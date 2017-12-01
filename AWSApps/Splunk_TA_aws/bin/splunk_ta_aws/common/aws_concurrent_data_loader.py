import threading
import Queue
from multiprocessing import Manager
from multiprocessing import Process
from multiprocessing import cpu_count
import os
import time
import traceback
import itertools
import splunksdc.log as logging
import splunktalib.event_writer as ew
import splunktalib.timer_queue as tq
import splunktalib.common.util as scutil
import splunktalib.orphan_process_monitor as opm
import splunktalib.data_loader_mgr as dlm

import splunk_ta_aws.common.ta_aws_consts as tac
import splunk_ta_aws.common.ta_aws_common as tacommon
import splunk_ta_aws.modinputs.kinesis.aws_kinesis_data_loader as akdl
import splunk_ta_aws.modinputs.cloudwatch.aws_cloudwatch_data_loader as acdl


logger = logging.get_module_logger()


def create_data_loader(config):

    service_2_data_loader = {
        tac.kinesis: akdl.KinesisDataLoader,
        tac.cloudwatch: acdl.CloudWatchDataLoader,
    }

    assert config.get(tac.aws_service)
    assert config[tac.aws_service] in service_2_data_loader

    return service_2_data_loader[config[tac.aws_service]](config)


def create_event_writer(config, process_safe):
    use_hec = scutil.is_true(config.get(tac.use_hec))
    use_raw_hec = scutil.is_true(config.get(tac.use_raw_hec))
    if use_hec or use_raw_hec:
        # if use hec, leave each worker process/thread to create event writer
        event_writer = None
    else:
        event_writer = ew.create_event_writer(config, process_safe)
        event_writer.start()
    return event_writer


def _wait_for_tear_down(tear_down_q, loader):
    checker = opm.OrphanProcessChecker()

    def do_wait():
        try:
            go_exit = tear_down_q.get(block=True, timeout=2)
        except Queue.Empty:
            go_exit = checker.is_orphan()
            if go_exit:
                logger.info("%s becomes orphan, going to exit", os.getpid())

        if go_exit and loader is not None:
            loader.stop()
        return go_exit
    return do_wait


def do_load_data(tear_down_q, task_configs):
    loaders = []
    event_writer = task_configs[0][tac.event_writer]
    if event_writer is None:
        event_writer = create_event_writer(task_configs[0], False)

    for task in task_configs:
        task[tac.event_writer] = event_writer
        loaders.append(create_data_loader(task))

    loader_mgr = dlm.create_data_loader_mgr(task_configs[0], event_writer)
    loader_mgr.add_timer(
        _wait_for_tear_down(tear_down_q, loader_mgr), time.time(), 3)
    loader_mgr.start(loaders)
    logger.info("End of load data")


def _load_data(tear_down_q, task_configs, log_ctx):
    try:
        if log_ctx:
            logging.RootHandler.teardown()
            logging.setup_root_logger(**log_ctx)
        do_load_data(tear_down_q, task_configs)
    except Exception:
        logger.error("Failed to load data, error=%s", traceback.format_exc())


class AwsConcurrentDataLoader(object):

    def __init__(self, task_configs, tear_down_q, process_safe, log_ctx):
        if process_safe:
            self._worker = Process(
                target=_load_data, args=(tear_down_q, task_configs, log_ctx))
        else:
            # FIXME threading pool
            self._worker = threading.Thread(
                target=_load_data, args=(tear_down_q, task_configs, None))

        self._worker.daemon = True
        self._started = False
        self._tear_down_q = tear_down_q

    def start(self):
        if self._started:
            return
        self._started = True

        self._worker.start()
        logger.info("AwsConcurrentDataLoader started.")

    def tear_down(self):
        self.stop()

    def stop(self):
        if not self._started:
            return
        self._started = False

        self._tear_down_q.put(True)
        logger.info("AwsConcurrentDataLoader is going to exit.")

    def join(self, timeout):
        self._worker.join(timeout)

    def terminate(self):
        if getattr(self._worker, "terminate"):
            self._worker.terminate()


class AwsDataLoaderManager(object):

    def __init__(self, task_configs, app_name, modular_name):
        self._task_configs = task_configs
        self._wakeup_queue = Queue.Queue()
        self._timer_queue = tq.TimerQueue()
        self._mgr = None
        self._started = False
        self._stop_signaled = False
        self._app_name = app_name
        self._modular_name = modular_name

    def start(self):
        if self._started:
            return
        self._started = True

        self._timer_queue.start()

        process_safe = self._use_multiprocess()
        logger.debug("Use multiprocessing=%s", process_safe)
        event_writer = create_event_writer(self._task_configs[0], process_safe)
        tear_down_q = self._create_tear_down_queue(process_safe)

        tasks = self._devide_tasks(event_writer)
        loaders = []
        for task_group, gid in zip(tasks, itertools.count()):
            log_ctx = {
                'app_name': self._app_name,
                'modular_name': self._modular_name,
                'stanza_name': str(gid)
            }
            loader = AwsConcurrentDataLoader(
                task_group, tear_down_q, process_safe, log_ctx
            )
            loader.start()
            loaders.append(loader)

        logger.info("AwsDataLoaderManager started")
        tacommon.setup_signal_handler(self, logger)
        tear_down = _wait_for_tear_down(self._wakeup_queue, None)
        while 1:
            go_exit = tear_down()
            if go_exit:
                break

        logger.info("AwsDataLoaderManager got stop signal")

        for loader in loaders:
            logger.info("Notify loader=%s", loader)
            loader.stop()

        for loader in loaders:
            try:
                loader.join(timeout=3)
            except Exception:
                logger.warn("Wait timeout, terminate loader=%s, error=%s",
                            loader, traceback.format_exc())
                loader.terminate()

        if event_writer is not None:
            event_writer.tear_down()
        self._timer_queue.tear_down()

        if self._mgr is not None:
            logger.info("ConcurrentMgr shutdown")
            self._mgr.shutdown()

        logger.info("AwsDataLoaderManager stopped")

    def tear_down(self):
        self.stop()

    def stop(self):
        self._stop_signaled = True
        self._wakeup_queue.put(True)
        logger.info("AwsDataLoaderManager is going to stop.")

    def stopped(self):
        return not self._started

    def received_stop_signal(self):
        return self._stop_signaled

    def add_timer(self, callback, when, interval):
        return self._timer_queue.add_timer(callback, when, interval)

    def remove_timer(self, timer):
        self._timer_queue.remove_timer(timer)

    @staticmethod
    def cpu_for_workers():
        process_num = cpu_count()
        # Reserve 3 CPU for splunkd
        if process_num > 3:
            process_num -= 3
        else:
            process_num = 1
        return process_num

    def _devide_tasks(self, event_writer):
        process_num = self.cpu_for_workers()
        if process_num > len(self._task_configs):
            process_num = len(self._task_configs)

        tasks = [[] for _ in xrange(process_num)]
        for i, task in enumerate(self._task_configs):
            task[tac.event_writer] = event_writer
            tasks[i % process_num].append(task)
        return tasks

    def _use_multiprocess(self):
        if not self._task_configs:
            return False

        return scutil.is_true(self._task_configs[0].get(tac.use_multiprocess))

    def _create_tear_down_queue(self, process_safe):
        if process_safe:
            self._mgr = Manager()
            tear_down_q = self._mgr.Queue()
        else:
            tear_down_q = Queue.Queue()
        return tear_down_q
