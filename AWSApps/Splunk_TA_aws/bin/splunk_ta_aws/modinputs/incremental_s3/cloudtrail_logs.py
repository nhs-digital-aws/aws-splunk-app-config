import cStringIO as StringIO
import re
import gzip
import json
import os
from splunksdc import logging
from .handler import AWSLogsTask


logger = logging.get_module_logger()


class CloudTrailLogsDelegate(object):
    @classmethod
    def build(cls, args):
        prefix = args.log_file_prefix
        start_date = args.log_start_date
        partitions = args.log_partitions

        if len(prefix) > 0 and not prefix.endswith('/'):
            prefix += '/'

        partitions = re.compile(partitions)

        return cls(prefix, start_date, partitions)

    def __init__(self, prefix, start_date, partitions):
        self._prefix = prefix
        self._start_date = start_date
        self._partitions = partitions

    def create_tasks(self, s3, bucket, namespace):
        partitions = self._enumerate_partitions(s3, bucket)
        logger.info("Discover partitions finished.", partitions=partitions)

        return [self._make_task(namespace, partition) for partition in partitions]

    def _enumerate_partitions(self, s3, bucket):
        partitions = list()
        prefix = self._prefix + 'AWSLogs/'
        for prefix in bucket.list_folders(s3, prefix):
            prefix += 'CloudTrail/'
            regions = bucket.list_folders(s3, prefix)
            regions = filter(self._interested, regions)
            partitions.extend(regions)
        return partitions

    def _interested(self, prefix):
        if not self._partitions:
            return True
        if self._partitions.match(prefix):
            return True
        return False

    def create_prefix(self, name, params):
        return params

    def create_initial_marker(self, name, params):
        return params + self._start_date.strftime('%Y/%m/%d/')

    def create_filter(self):
        return self._filter

    def create_decoder(self):
        return self._decode

    @classmethod
    def _filter(cls, files):
        return [item for item in files if item.key.endswith('.json.gz')]

    @classmethod
    def _decode(cls, job, content):
        compressed = StringIO.StringIO()
        compressed.write(content)
        compressed.seek(0)

        decompressed = gzip.GzipFile(fileobj=compressed, mode='rb')
        content = json.load(decompressed)
        decompressed.close()
        compressed.close()
        records = '\n'.join([json.dumps(item) for item in content.get('Records', [])])
        return records

    @classmethod
    def _make_task(cls, namespace, partition):
        suffix = partition
        suffix = suffix.lower().replace('/', '_')
        suffix = suffix[:-1]
        name = os.path.join(namespace, suffix)
        return AWSLogsTask(name, partition)
