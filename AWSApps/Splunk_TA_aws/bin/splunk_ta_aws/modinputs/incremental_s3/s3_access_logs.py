from splunksdc import logging
from .handler import AWSLogsTask


logger = logging.get_module_logger()


class S3AccessLogsDelegate(object):
    @classmethod
    def build(cls, args):
        prefix = args.log_file_prefix
        start_date = args.log_start_date

        return cls(prefix, start_date)

    def __init__(self, prefix, start_date):
        self._prefix = prefix
        self._start_date = start_date

    def create_tasks(self, s3, bucket, namespace):
        return [AWSLogsTask(namespace, None)]

    def create_prefix(self, name, params):
        return self._prefix

    def create_initial_marker(self, name, params):
        marker = self._prefix + self._start_date.strftime('%Y-%m-%d-')
        return marker

    def create_filter(self):
        return self._filter

    def create_decoder(self):
        return self._decode

    @classmethod
    def _filter(cls, files):
        return files

    @classmethod
    def _decode(cls, job, content):
        return content
