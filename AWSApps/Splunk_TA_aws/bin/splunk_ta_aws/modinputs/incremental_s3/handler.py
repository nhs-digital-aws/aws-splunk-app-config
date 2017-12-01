from collections import namedtuple
import os
import boto3.session
import botocore.exceptions
import botocore.endpoint
from splunksdc import logging
from splunksdc.batch import BatchExecutor
from splunksdc.utils import LogExceptions
from .adapter import AWSLogsPipelineAdapter


logger = logging.get_module_logger()


AWSLogsTask = namedtuple('AWSLogsTask', ('name', 'params'))


class AWSLogsHandler(object):
    _EXCEPTIONS = (
        IOError,
        botocore.exceptions.BotoCoreError,
        botocore.exceptions.ClientError,
    )

    def __init__(self, settings, proxy, data_input_name, metadata, options, bucket, delegate, credentials):
        self._settings = settings
        self._proxy = proxy
        self._data_input_name = data_input_name
        self._metadata = metadata
        self._options = options
        self._bucket = bucket
        self._delegate = delegate
        self._credentials = credentials

    def run(self, app, config):
        data_input_name = self._data_input_name
        opt = self._options
        bucket = self._bucket
        session = boto3.session.Session()
        s3 = bucket.client(self._credentials, session)
        tasks = self._delegate.create_tasks(s3, bucket, data_input_name)
        scheduler = app.create_task_scheduler(self.run_task)
        scheduler.set_max_number_of_worker(opt.max_number_of_process)
        for name, params in tasks:
            scheduler.add_task(name, params, 0)

        scheduler.run([app.is_aborted, config.has_expired])
        return 0

    # A pickable wrapper of perform
    def run_task(self, app, name, params):
        return self.perform(app, name, params)

    @LogExceptions(logger, 'Task was interrupted by an unhandled exception.', lambda e: -1)
    def perform(self, app, name, params):
        if os.name == 'nt':
            self._settings.setup_log_level()
            self._proxy.hook_boto3_get_proxies()

        metadata = self._metadata
        opt = self._options
        bucket = self._bucket
        prefix = self._delegate.create_prefix(name, params)
        marker = self._delegate.create_initial_marker(name, params)
        key_filter = self._delegate.create_filter()
        decoder = self._delegate.create_decoder()
        credentials = self._credentials

        event = app.create_event_writer(**vars(metadata))
        with app.open_checkpoint(name) as checkpoint:
            while not app.is_aborted():
                # refresh credential in case it has expired.
                credentials.refresh()
                adapter = AWSLogsPipelineAdapter(
                    app, credentials, prefix, marker, key_filter, decoder,
                    event, checkpoint, bucket, opt.max_retries, opt.max_fails
                )
                pipeline = BatchExecutor(number_of_threads=opt.max_number_of_thread)
                if pipeline.run(adapter):
                    # no more new files
                    break
        return 0









