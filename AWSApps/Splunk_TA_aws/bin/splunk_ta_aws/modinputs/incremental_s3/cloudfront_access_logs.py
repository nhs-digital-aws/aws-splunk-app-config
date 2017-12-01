import cStringIO as StringIO
from datetime import datetime
import gzip
from splunksdc import logging
from .handler import AWSLogsTask


logger = logging.get_module_logger()


class CloudFrontAccessLogsDelegate(object):
    @classmethod
    def build(cls, args):
        prefix = args.log_file_prefix
        start_date = args.log_start_date
        name_format = args.log_name_format

        s1 = datetime(1970, 1, 1).strftime(name_format)
        s2 = datetime(2010, 10, 10).strftime(name_format)
        filename = ''
        for x, y in zip(s1, s2):
            if x != y:
                break
            filename += x

        return cls(prefix, start_date, filename)

    def __init__(self, prefix, start_date, filename):
        self._prefix = prefix
        self._start_date = start_date
        self._filename = filename

    def create_tasks(self, s3, bucket, namespace):
        return [AWSLogsTask(namespace, None)]

    def create_prefix(self, name, params):
        prefix = self._prefix + self._filename
        return prefix

    def create_initial_marker(self, name, params):
        prefix = self.create_prefix(name, params)
        marker = prefix + self._start_date.strftime('%Y-%m-%d-')
        return marker

    def create_filter(self):
        return self._filter

    def create_decoder(self):
        return self._decode

    @classmethod
    def _filter(cls, files):
        return [item for item in files if item.key.endswith('.gz')]

    @classmethod
    def _decode(cls, job, content):
        compressed = StringIO.StringIO()
        compressed.write(content)
        compressed.seek(0)

        decompressed = gzip.GzipFile(fileobj=compressed, mode='rb')
        content = decompressed.read()
        decompressed.close()
        compressed.close()

        return content
