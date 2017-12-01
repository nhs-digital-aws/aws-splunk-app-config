import argparse
from collections import deque
import random
import time
import os
import os.path
import sys
import multiprocessing
from splunklib.client import Service
from splunklib.modularinput.scheme import ET
from splunklib.modularinput.validation_definition import ValidationDefinition
from splunklib.modularinput.scheme import Scheme
from splunklib.modularinput.argument import Argument
from splunksdc.context import Context
from splunksdc.event_writer import XMLEventWriter, HECWriter
from splunksdc.checkpoint import LocalKVStore
from splunksdc.utils import FSLock
from splunksdc.scheduler import TaskScheduler
from splunksdc.config import ConfigManager
from splunksdc.loop import LoopFactory
from splunksdc import log as logging


logger = logging.get_module_logger()


def _parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scheme", action='store_true')
    parser.add_argument("--validate-arguments", action='store_true')
    parser.add_argument("--server_uri", metavar="SPLUNK_URI")
    parser.add_argument("--stanza", metavar="STANZA")
    parser.add_argument("--app_name", metavar="APP_NAME")
    return parser.parse_args()


def _build_scheme(title, use_single_instance, **kwargs):
    scheme = Scheme(title)
    scheme.description = kwargs.pop('description', None)
    scheme.use_external_validation = True
    scheme.streaming_mode = Scheme.streaming_mode_xml
    scheme.use_single_instance = use_single_instance
    for name, options in kwargs.pop('arguments', {}).items():
        description = options.pop('description', None)
        validation = options.pop('validation', None)
        data_type = options.pop('data_type', Argument.data_type_string)
        required_on_edit = options.pop('required_on_edit', False)
        required_on_create = options.pop('required_on_create', False)
        title = options.pop('title', None)
        argument = Argument(
            name, description, validation, data_type,
            required_on_edit, required_on_create, title
        )
        scheme.add_argument(argument)

    return scheme


def _render_scheme(stream, scheme):
    data = ET.tostring(scheme.to_xml())
    stream.write(data)
    stream.flush()
    return 0


def _validate_definition(stream, scheme):
    definition = ValidationDefinition.parse(stream)
    return 0


def _extract_app_name_from_path(path):
    path, name = os.path.split(path)
    path, name = os.path.split(path)
    path, name = os.path.split(path)
    return name


def _extract_modular_name_from_path(path):
    _, name = os.path.split(path)
    return name[:-3]


def run_modular_input(modular_input_factory, **kwargs):

    wait_time = random.uniform(0, 5)
    time.sleep(wait_time)

    modular_input_path = sys.argv[0]
    args = _parse_args()
    app_name = args.app_name
    if not app_name:
        app_name = _extract_app_name_from_path(modular_input_path)

    modular_name = _extract_modular_name_from_path(modular_input_path)

    use_single_instance = kwargs.pop('use_single_instance', True)
    app_title = kwargs.pop('title', app_name)
    log_file_sharding = kwargs.pop('log_file_sharding', False)

    scheme = _build_scheme(app_title, use_single_instance, **kwargs)

    if args.scheme:
        code = _render_scheme(sys.stdout, scheme)
        sys.exit(code)
    elif args.validate_arguments:
        code = _validate_definition(sys.stdin, scheme)
        sys.exit(code)

    if args.server_uri:
        context = Context.from_url(args.server_uri, args.stanza)
    else:
        context = Context.from_stream(sys.stdin)

    loop = LoopFactory.create()
    app = modular_input_factory(loop, app_name, modular_name, context, use_single_instance)
    suffix = 0 if log_file_sharding else None
    app.setup_root_logger(suffix)
    code = app.run()
    sys.exit(code)


class SimpleCollectorTask(object):
    def __init__(self, identifier, callback, app):
        self._app = app
        self._callback = callback
        self._identifier = identifier
        self._worker = None

    def start(self, name, params):
        master_context = logging.ThreadLocalLoggingStack.top()
        args = (self._identifier, master_context, self._callback, self._app, name, params)
        worker = multiprocessing.Process(
            target=self._task_procedure, args=args
        )
        worker.daemon = True
        self._worker = worker
        self._worker.start()

    def poll(self):
        worker = self._worker
        if not worker:
            return True
        worker.join(0)
        return not worker.is_alive()

    def end(self):
        if self._worker:
            self._worker.terminate()
            self._worker = None

    @classmethod
    def _task_procedure(cls, identifier, master_context, callback, app, name, params):
        prefix = '' if not os.name == 'nt' else master_context
        logging.RootHandler.teardown()
        app.setup_root_logger(identifier)
        with logging.LogContext(prefix=prefix):
            callback(app, name, params)


class SimpleCollectorTaskFactory(object):
    def __init__(self, app, callback):
        self._app = app
        self._callback = callback
        self._pool = deque()
        self._next_id = 1

    def create(self, name, params):
        workspace = self._app.workspace()
        fullname = os.path.join(workspace, name)
        folder = os.path.dirname(fullname)
        if not os.path.exists(folder):
            os.makedirs(folder)

        worker = self._acquire_worker()
        worker.start(name, params)
        return worker

    def release(self, worker):
        worker.end()
        self._pool.append(worker)

    def _acquire_worker(self):
        if not len(self._pool):
            return self._new_worker()
        return self._pool.popleft()

    def _new_worker(self):
        identifier = self._next_id
        self._next_id += 1
        return SimpleCollectorTask(identifier, self._callback, self._app)


class SimpleCollectorV1(object):
    @classmethod
    def main(cls, delegate, **kwargs):
        def factory(loop, app_name, modular_name, context, use_single_instance):
            return cls(loop, app_name, modular_name, context, use_single_instance, delegate)

        run_modular_input(factory, **kwargs)

    def __init__(self, loop, app_name, modular_name, context, use_single_instance, delegate):
        self._app_name = app_name
        self._modular_name = modular_name
        self._context = context
        self._delegate = delegate
        self._stdout_lock = multiprocessing.RLock()
        self._logging_lock = multiprocessing.RLock()
        self._use_single_instance = use_single_instance
        self._loop = loop

    def setup_root_logger(self, shard=None):
        stanza_name = ''
        if not self._use_single_instance:
            stanza = self.inputs()[0]
            stanza_name = stanza.name
        if shard is not None:
            stanza_name += '_' + str(shard)
        factory = logging.RotatingFileHandlerFactory(
            self._app_name, self._modular_name, stanza_name
        )
        logging.RootHandler.setup(factory)

    def _sylock(self, path):
        filename = ''
        if not self._use_single_instance:
            stanza = self.inputs()[0]
            filename += stanza.name

        filename += '.lock'
        filename = os.path.join(path, filename)
        return FSLock.open(filename)

    def _ensure_checkpoint_folder(self):
        path = self._context.checkpoint_dir
        if not os.path.exists(path):
            os.makedirs(path)
        return path

    def abort(self):
        self._loop.abort()

    def run(self):
        folder = self._ensure_checkpoint_folder()
        with self._sylock(folder):
            logger.info('Modular input started.')
            config = self.create_config_service()
            exitcode = self._delegate(self, config)
            logger.info('Modular input exited.')
            return exitcode

    def create_task_scheduler(self, callback):
        factory = SimpleCollectorTaskFactory(self, callback)
        return TaskScheduler(factory)

    def open_checkpoint(self, name):
        workspace = self._context.checkpoint_dir
        fullname = os.path.join(workspace, name + '.ckpt')
        checkpoint = LocalKVStore.open_always(fullname)
        return checkpoint

    def create_event_writer(self, url=None, **metadata):
        if url:
            return HECWriter(url, **metadata)
        return XMLEventWriter(self._stdout_lock, sys.stdout, **metadata)

    def create_splunk_service(self):
        app_name = self._app_name
        context = self._context
        service = Service(
            scheme=context.server_scheme,
            host=context.server_host,
            port=context.server_port,
            token=context.token,
            owner='nobody',
            app=app_name,
        )
        return service

    def create_config_service(self):
        splunk = self.create_splunk_service()
        config = ConfigManager(splunk)
        return config

    def workspace(self):
        return self._context.checkpoint_dir

    def inputs(self):
        return self._context.inputs

    def is_aborted(self):
        return self._loop.is_aborted()



