from datetime import timedelta
import os.path
import re
import json
import shutil
import time
import tempfile
import threading
import uuid
import urllib
from collections import OrderedDict
import boto3.session
import botocore.exceptions
from splunksdc import logging
from splunksdc.batch import BatchExecutor, BatchExecutorExit
from splunksdc.config import StanzaParser, IntegerField, StringField, LogLevelField
from splunksdc.utils import LogExceptions, LogWith
from splunk_ta_aws import set_log_level
from splunk_ta_aws.common.proxy import ProxySettings
from splunk_ta_aws.common.credentials import AWSCredentialsProviderFactory, AWSCredentialsCache
from splunk_ta_aws.common.decoder import DecoderFactory
from splunk_ta_aws.common.sqs import SQSQueue
from splunk_ta_aws.common.s3 import S3Bucket


logger = logging.get_module_logger()


class Job(object):
    def __init__(self, message, created, ttl):
        self._message = message
        self._created = created
        self._ttl = ttl
        self._job_id = uuid.uuid4()

    @property
    def message(self):
        return self._message

    @property
    def brief(self):
        return {
            'message_id': self._message.message_id,
            'created': self._created,
            'ttl': self._ttl,
            'job_id': self._job_id,
        }

    def is_expired(self):
        now = time.time()
        return now - self._created >= self._ttl


class S3Notice(object):
    """
    A wrapper class for easy access the dict based s3 notification.
    """
    def __init__(self, region, bucket, key, size, etag):
        self._region = region
        self._bucket = bucket
        self._key = key
        self._size = size
        self._etag = etag

    @property
    def region(self):
        return self._region

    @property
    def bucket(self):
        return self._bucket

    @property
    def key(self):
        return self._key

    @property
    def size(self):
        return self._size

    @property
    def etag(self):
        return self._etag

    @property
    def source(self):
        return 's3://' + self.bucket + '/' + self.key


class S3NoticeParser(object):
    def __init__(self, message):
        self._message = message

    def parse(self):
        message = self._message
        records = message['Records']
        # ignore events which doesn't match with ObjectCreated:*.
        records = [self._make(record) for record in records if self._eoi(record)]
        # ignore empty files or size is unknown.
        records = [item for item in records if item.size]
        return records

    @classmethod
    def _eoi(cls, record):
        return record['eventName'].startswith('ObjectCreated:')

    @classmethod
    def _make(cls, record):
        s3 = record['s3']
        s3bucket = s3['bucket']
        s3object = s3['object']
        region = record['awsRegion']
        bucket = s3bucket['name']
        key = urllib.unquote(s3object['key'].encode('utf-8')).decode('utf-8')
        # size and etag may not exist in some events.
        size = s3object.get('size')
        etag = s3object.get('eTag')
        return S3Notice(region, bucket, key, size, etag)


class ConfigNoticeParser(object):
    """
    Wrapper class for easy accessing config dict
    based notifications.
    """
    _SUPPORTED_MESSAGE_TYPE = [
        'ConfigurationHistoryDeliveryCompleted',
        'ConfigurationSnapshotDeliveryCompleted',
    ]

    _UNSUPPORTED_MESSAGE_TYPE = [
        'ConfigurationItemChangeNotification',
        'ConfigurationSnapshotDeliveryStarted',
        'ComplianceChangeNotification',
        'ConfigRulesEvaluationStarted',
    ]

    def __init__(self, message, region_cache):
        self._message = message
        self._region_cache = region_cache

    def parse(self):
        message = self._message
        message_type = message['messageType']
        if message_type in self._UNSUPPORTED_MESSAGE_TYPE:
            logger.info('Ingnoring this config message.',
                        message_type=message_type)
            return []

        if message_type not in self._SUPPORTED_MESSAGE_TYPE:
            raise TypeError('Unknown config message.')

        # for supported message types
        bucket = message['s3Bucket']
        region = self._region_cache.get_region(bucket)
        key = message['s3ObjectKey']
        if not isinstance(key, unicode):
            raise TypeError('s3ObjectKey is expected to be an unicode object.')
        return [self._make(region, bucket, key)]

    def _make(self, region, bucket, key):
        return S3Notice(region, bucket, key, None, None)


class CloudtrailNoticeParser(object):
    """
    Wrapper class for easy accessing cloudtrail
    dict based notifications.
    """
    def __init__(self, message, region_cache):
        self._message = message
        self._region_cache = region_cache

    def parse(self):
        message = self._message
        bucket = message['s3Bucket']
        region = self._region_cache.get_region(bucket)
        keys = message['s3ObjectKey']
        if not isinstance(keys, list):
            raise TypeError('s3ObjectKey is expected to be a list object.')
        return [self._make(region, bucket, key) for key in keys]

    def _make(self, region, bucket, key):
        return S3Notice(region, bucket, key, None, None)


class SQSBasedS3PipelineAdapter(object):
    _MAX_CHUNK_SIZE = 1048576
    _MIN_TTL = timedelta(seconds=600)

    def __init__(self, app, config, credentials, sqs_agent, s3_agent, s3_region_cache,
                 decode, event_writer, max_receive_count, exit_on_idle, temp_folder):
        self._app = app
        self._config = config
        self._credentials = credentials
        self._sqs_agent = sqs_agent
        self._s3_agent = s3_agent
        self._region_cache = s3_region_cache
        self._decode = decode
        self._event_writer = event_writer
        self._idle_count = 0
        self._exit_on_idle = exit_on_idle
        self._temp_folder = temp_folder
        self._max_receive_count = max_receive_count
        self._max_memory_file_size = 8 * 1024 * 1024
        self._clock = time.time

    def is_aborted(self):
        if self._config.has_expired():
            return True
        return self._app.is_aborted()

    def discover(self):
        credentials = self._credentials
        attributes = self._sqs_agent.get_attributes()
        ttl = attributes.visibility_timeout
        clock = self._clock

        if not attributes.redrive_policy:
            logger.error('Dead letter queue not found.')
            yield BatchExecutorExit(True)

        while True:
            if credentials.need_retire(self._MIN_TTL):
                credentials.refresh()

            messages = self._sqs_agent.get_messages()
            now = clock()
            if self._should_exit(messages):
                yield BatchExecutorExit(True)

            # Ignore messages which have been seen a lot of times
            messages = [item for item in messages if not self._should_ignore(item)]
            yield [Job(message, now, ttl) for message in messages]

    def do(self, job, session):
        with logging.LogContext(**job.brief):
            self._process(job.is_expired, job.message, session)

    def _process(self, is_expired, message, session):
        try:
            if is_expired():
                return logger.error('Visibility timeout expired.')

            records = self._parse(message)
            number_of_record = len(records)
            if not number_of_record:
                return logger.warning('There\'s no files need to be processed in this message.')

            for i in range(number_of_record):
                record = records[i]
                with self._open_temp_file() as cache:
                    headers = self._download(record, cache, session)
                    # Check visibility timeout before ingest the first file.
                    # Ingest remain files without check visibility timeout again.
                    if i == 0 and is_expired():
                        return logger.error('Visibility timeout expired before sent data for indexing.')
                    self._ingest_file(cache, record, headers)

            self._delete_message(message, session)
            if is_expired():
                files = [record.source for record in records]
                logger.warning('File has been ingested beyond the visibility timeout.', files=files)
        except Exception as e:
            logger.critical('An error occurred while processing the message.', exc_info=True)
            return e

    def done(self, job, result):
        pass

    def allocate(self):
        return boto3.session.Session()

    def _ingest_file(self, fileobj, record, headers):
        try:
            source = record.source.encode('utf-8')
            for records, metadata in self._decode(fileobj, source):
                metadata = vars(metadata)
                volume = self._event_writer.write_fileobj(records, **metadata)
                self._index_summary(headers, source, volume)
        except:
            logger.error('Failed to ingest file.', uri=record.source)
            raise

    def _download(self, record, cache, session):
        try:
            return self._s3_agent.download(record, cache, session)
        except (botocore.exceptions.ClientError, IOError):
            logger.error('Failed to download file.', uri=record.source)
            raise

    def _parse(self, message):
        try:
            document = json.loads(message.body)
            if 'TopicArn' in document:
                document = json.loads(document['Message'])

            records = None
            parsers = (
                S3NoticeParser(document),
                CloudtrailNoticeParser(document, self._region_cache),
                ConfigNoticeParser(document, self._region_cache)
            )
            for parser in parsers:
                try:
                    records = parser.parse()
                    break
                except (KeyError, ValueError, TypeError):
                    continue

            if records is None:
                raise ValueError("Unable to parse message.")
            return records
        except:
            logger.error('Failed to parse message.')
            raise

    def _should_exit(self, messages):
        if not messages:
            self._idle_count += 1
            if self._idle_count >= self._exit_on_idle:
                return True
            return False
        self._idle_count = 0
        return False

    def _should_ignore(self, message):
        return 0 > self._max_receive_count > message.receive_count

    def _open_temp_file(self):
        try:
            max_size = self._max_memory_file_size
            folder = self._temp_folder
            return tempfile.SpooledTemporaryFile(max_size=max_size, dir=folder)
        except:
            logger.error('Failed to open temporary file.')
            raise

    def _delete_message(self, message, session):
        try:
            self._sqs_agent.delete_message(message, session)
        except:
            logger.error('Failed to delete message.')
            raise

    @staticmethod
    def _index_summary(response, source, volume):
        last_modified = response.last_modified.strftime('%Y-%m-%dT%H:%M:%SZ')
        logger.info(
            'Sent data for indexing.', size=volume,
            last_modified=last_modified, key=source
        )


class SQSAgent(object):
    def __init__(self, url, region, credentials):
        self._queue = SQSQueue(url, region)
        self._batch_size = 0
        self._credentials = credentials

    def get_messages(self, session=None):
        client = self._queue.client(self._credentials, session)
        return self._queue.get_messages(client, self._batch_size)

    def delete_message(self, message, session=None):
        client = self._queue.client(self._credentials, session)
        return self._queue.delete_message(client, message)

    def get_attributes(self, session=None):
        client = self._queue.client(self._credentials, session)
        return self._queue.get_attributes(client)

    def set_batch_size(self, value):
        self._batch_size = value


class S3RegionCache(object):

    def __init__(self, credentials, default_region):
        self._credentials = credentials
        self._lock = threading.Lock()
        self._region = default_region
        self._s3_region_cache = OrderedDict()

    def get_region(self, bucket, session=None):
        with self._lock:
            if bucket in self._s3_region_cache:
                return self._s3_region_cache[bucket]
            else:
                client = self._credentials.client('s3v4', self._region, session)
                s3_region = client.get_bucket_location(Bucket=bucket).get('LocationConstraint')
                self._s3_region_cache[bucket] = s3_region
                return s3_region


class S3Agent(object):
    def __init__(self, credentials):
        self._multipart_threshold = 0
        self._credentials = credentials

    def download(self, notice, fileobj, session=None):
        bucket = S3Bucket(notice.bucket, notice.region)
        s3 = bucket.client(self._credentials, session)
        etag = notice.etag
        key = notice.key
        condition = {} if not etag else {'IfMatch': etag}
        if self._should_multipart_download(notice):
            return bucket.transfer(s3, key, fileobj, **condition)
        return bucket.fetch(s3, key, fileobj, **condition)

    def set_multipart_threshold(self, value):
        self._multipart_threshold = value

    def _should_multipart_download(self, notice):
        if not notice.size:
            # for config and cloudtrail based sqs message,
            # size is unavailable, directly do multipart
            return True
        # for s3 based sqs message
        elif notice.size >= self._multipart_threshold:
            return True
        return False


class SQSBasedS3Settings(object):
    @classmethod
    def load(cls, config):
        content = config.load('aws_settings', stanza='aws_sqs_based_s3')
        parser = StanzaParser([
            LogLevelField('log_level', default='WARNING')
        ])
        settings = parser.parse(content)
        return cls(settings)

    def __init__(self, settings):
        self._settings = settings

    def setup_log_level(self):
        set_log_level(self._settings.log_level)


class SQSBasedS3DataInput(object):
    def __init__(self, stanza):
        self._kind = stanza.kind
        self._name = stanza.name
        self._args = stanza.content
        self._start_time = int(time.time())

    def create_metadata(self):
        stanza = self._kind + '://' + self._name
        parser = StanzaParser([
            StringField('index'),
            StringField('host'),
            StringField('stanza', fillempty=stanza)
        ])
        return self._extract_arguments(parser)

    def create_credentials(self, config):
        parser = StanzaParser([
            StringField('aws_account', required=True),
            StringField('aws_iam_role'),
        ])
        args = self._extract_arguments(parser)
        factory = AWSCredentialsProviderFactory(config)
        provider = factory.create(args.aws_account, args.aws_iam_role)
        credentials = AWSCredentialsCache(provider)
        return credentials

    def create_file_decoder(self):
        parser = StanzaParser([
            StringField('s3_file_decoder', rename='name', required=True),
            StringField('sourcetype', default='')
        ])
        args = self._extract_arguments(parser)
        factory = DecoderFactory.create_default_instance()
        return factory.create(**vars(args))

    def create_sqs_agent(self, credential):
        parser = StanzaParser([
            StringField('sqs_queue_url', required=True),
            StringField('sqs_queue_region', required=True),
            IntegerField('sqs_batch_size', default=10, lower=1, upper=10),
        ])
        args = self._extract_arguments(parser)
        agent = SQSAgent(args.sqs_queue_url, args.sqs_queue_region, credential)
        agent.set_batch_size(args.sqs_batch_size)
        return agent

    def create_s3_agent(self, credential):
        _1MB = 1024 * 1024
        _8MB = _1MB * 8
        _64MB = _8MB * 8
        parser = StanzaParser([
            IntegerField('s3_multipart_threshold', default=_8MB, lower=_8MB, upper=_64MB)
        ])
        args = self._extract_arguments(parser)
        agent = S3Agent(credential)
        agent.set_multipart_threshold(args.s3_multipart_threshold)
        return agent

    def create_region_cache(self, credentials):
        parser = StanzaParser([
            StringField('sqs_queue_region', required=True)
        ])
        args = self._extract_arguments(parser)
        return S3RegionCache(credentials, args.sqs_queue_region)

    def create_event_writer(self, app):
        metadata = self.create_metadata()
        parser = StanzaParser([StringField('use_raw_hec')])
        args = self._extract_arguments(parser)
        url = args.use_raw_hec
        return app.create_event_writer(url, **vars(metadata))

    def create_batch_executor(self):
        parser = StanzaParser([
            IntegerField('sqs_batch_size', rename='number_of_threads',
                         default=10, lower=1, upper=10),
        ])
        args = self._extract_arguments(parser)
        return BatchExecutor(number_of_threads=args.number_of_threads)

    def parse_options(self):
        parser = StanzaParser([
            IntegerField('max_receive_count', default=-1),
            IntegerField('exit_on_idle', default=15),
        ])
        return self._extract_arguments(parser)

    def _extract_arguments(self, parser):
        return parser.parse(self._args)

    def create_temp_folder(self, app):
        # clean all temp files at startup.
        temp_folder = os.path.join(app.workspace(), self._name)
        shutil.rmtree(temp_folder, ignore_errors=True)
        if not os.path.exists(temp_folder):
            os.makedirs(temp_folder)
        return temp_folder

    @property
    def name(self):
        return self._name

    @property
    def start_time(self):
        return self._start_time

    @LogWith(datainput=name, start_time=start_time)
    @LogExceptions(logger, 'Data input was interrupted by an unhandled exception.', lambda e: -1)
    def run(self, app, config):
        settings = SQSBasedS3Settings.load(config)
        settings.setup_log_level()
        proxy = ProxySettings.load(config)
        proxy.hook_boto3_get_proxies()

        logger.info('Data input started.', **self._args)

        credentials = self.create_credentials(config)
        sqs_agent = self.create_sqs_agent(credentials)
        s3_agent = self.create_s3_agent(credentials)
        s3_region_cache = self.create_region_cache(credentials)
        decoder = self.create_file_decoder()
        options = self.parse_options()

        event_writer = self.create_event_writer(app)
        temp_folder = self.create_temp_folder(app)
        executor = self.create_batch_executor()
        components = {
            'app': app,
            'config': config,
            'credentials': credentials,
            'sqs_agent': sqs_agent,
            's3_agent': s3_agent,
            's3_region_cache': s3_region_cache,
            'decode': decoder,
            'event_writer': event_writer,
            'max_receive_count': options.max_receive_count,
            'exit_on_idle': options.exit_on_idle,
            'temp_folder': temp_folder,
        }
        adapter = SQSBasedS3PipelineAdapter(**components)
        executor.run(adapter)
        return 0
