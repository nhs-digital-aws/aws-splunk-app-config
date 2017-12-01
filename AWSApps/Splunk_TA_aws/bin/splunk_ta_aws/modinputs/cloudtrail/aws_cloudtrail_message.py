
import io
import re
import gzip
import json
import time
import calendar
import traceback
import threading
from splunksdc import logging
from aws_cloudtrail_common import CloudTrailProcessorError
import aws_cloudtrail_common as ctcommon


logger = logging.get_module_logger()


def get_processor(message):
    """
    Process message.

    :param message:
    :return:
    :rtype: MessageProcessor
    """

    processors = (CloudTrailMessage, S3Message)
    for processor in processors:
        if processor.validate(message):
            return processor()
    else:
        raise CloudTrailProcessorError(
            'Invalid CloudTrail message. Please check SQS settings.')


class S3ConnectionPool(object):
    """
    S3 Bucket Pool: one S3 connection for each bucket.
    """

    _pool = {}
    _lock = threading.Lock()

    @staticmethod
    def get_bucket(session_key, key_id, secret_key, bucket_name, key_name):
        with S3ConnectionPool._lock:
            if bucket_name not in S3ConnectionPool._pool:
                S3ConnectionPool._pool[bucket_name] = \
                    ctcommon.create_s3_connection(
                        bucket_name, key_name, key_id, secret_key, session_key)
        return S3ConnectionPool._pool[bucket_name].get_bucket(
            bucket_name, validate=False)


class MessageProcessor(object):

    __metaclass__ = ctcommon.ThreadLocalSingleton

    WRITEN = 'writen'
    REDIRECTED = 'redirected'
    DISCARDED = 'discarded'

    def run(self, session_key, datainput, aws_account, message_id, message,
            blacklist_pattern, excluded_events_index, remove_files_when_done,
            sourcetype, index):
        """
        Process Message.

        :param session_key:
        :param datainput
        :param aws_account:
        :param message_id:
        :param message:
        :param blacklist_pattern:
        :param excluded_events_index:
        :param remove_files_when_done:
        :return:
        """
        self._setup(session_key, datainput, aws_account, message_id, message,
                    blacklist_pattern, excluded_events_index,
                    remove_files_when_done, sourcetype, index)
        for bucket_name, key_name in self._s3_keys():
            logger.debug('Retrieve from S3 Started',
                         datainput=self.datainput, message_id=self.message_id,
                         s3_bucket_name=bucket_name, s3_key_name=key_name)
            try:
                res = self._process_s3_key(bucket_name, key_name)
            except Exception:
                logger.error('Retrieve from S3 Failed',
                             datainput=self.datainput,
                             s3_bucket_name=bucket_name, s3_key_name=key_name,
                             error=traceback.format_exc())
                continue
            logger.debug('Retrieve from S3 Finished', datainput=self.datainput,
                         message_id=self.message_id, s3_bucket_name=bucket_name,
                         s3_key_name=key_name, **res)
        self._teardown()

    @staticmethod
    def get_s3_key_record_time(record):
        time_str = record['eventTime'].replace('Z', 'GMT')
        time_obj = time.strptime(time_str, '%Y-%m-%dT%H:%M:%S%Z')
        return int(calendar.timegm(time_obj))

    def _load_s3_key(self, bucket_name, key_name):
        # Get S3 key
        s3_bucket = S3ConnectionPool.get_bucket(
            self.session_key, self.aws_account['key_id'],
            self.aws_account['secret_key'], bucket_name, key_name)
        s3_key = s3_bucket.get_key(key_name, validate=False)

        # Load S3 key
        s3_key_cont = {}
        if s3_key is not None:
            with io.BytesIO(s3_key.read()) as bio:
                with gzip.GzipFile(fileobj=bio) as gz:
                    s3_key_cont = json.loads(gz.read())

        # Remove S3 key if required
        if self.remove_files_when_done:
            logger.debug('Remove S3 Key', datainput=self.datainput,
                         message_id=self.message_id,
                         s3_bucket_name=bucket_name, s3_key_name=key_name)
            mdr = s3_bucket.delete_keys([key_name], quiet=True)
            if mdr.errors:
                logger.error('Remove S3 Key Failed', datainput=self.datainput,
                             message_id=self.message_id,
                             s3_bucket_name=bucket_name, s3_key_name=key_name)
        return s3_key_cont

    def _process_s3_key(self, bucket_name, key_name):
        logger.debug('Start getting S3 key', datainput=self.datainput,
                     s3_bucket_name=bucket_name, s3_key_name=key_name)

        s3_key_cont = self._load_s3_key(bucket_name, key_name)
        stats = {
            MessageProcessor.WRITEN: 0,
            MessageProcessor.REDIRECTED: 0,
            MessageProcessor.DISCARDED: 0,
        }

        logger.debug('End of getting S3 key', datainput=self.datainput,
                     s3_bucket_name=bucket_name, s3_key_name=key_name)

        events = []
        for rec in s3_key_cont.get('Records', []):
            res = self._process_s3_key_record(
                bucket_name, key_name, rec, events)
            stats[res] += 1

        logger.debug('End of processing records', datainput=self.datainput,
                     s3_bucket_name=bucket_name, s3_key_name=key_name)

        ctcommon.event_writer.write_events(events)
        ctcommon.orphan_check()

        logger.debug('End of writting events', datainput=self.datainput,
                     s3_bucket_name=bucket_name, s3_key_name=key_name)
        return stats

    def _process_s3_key_record(self, bucket_name, key_name, record, events):
        if not self.blacklist_pattern or not self.blacklist_pattern.search(record['eventName']):
            rec = ctcommon.event_writer.create_event(
                json.dumps(record),
                index=self.index,
                source='s3://{}/{}'.format(bucket_name, key_name),
                sourcetype=self.sourcetype)
            events.append(rec)
            return MessageProcessor.WRITEN
        elif self.excluded_events_index:
            rec = ctcommon.event_writer.create_event(
                json.dumps(record),
                index=self.excluded_events_index,
                source='s3://{}/{}'.format(bucket_name, key_name),
                sourcetype=self.sourcetype)
            events.append(rec)
            return MessageProcessor.REDIRECTED
        else:
            logger.info('Blacklisted Event', datainput=self.datainput,
                        message_id=self.message_id,
                        bucket_name=bucket_name, key_name=key_name,
                        event_name=record['eventName'],
                        event_time=record['eventTime'])
            return MessageProcessor.DISCARDED

    def _setup(self, session_key, datainput, aws_account, message_id, message,
               blacklist_pattern, excluded_events_index,
               remove_files_when_done, sourcetype, index):
        self.session_key = session_key
        self.datainput = datainput
        self.aws_account = aws_account
        self.message_id = message_id
        self.message = message
        if blacklist_pattern:
            blacklist_pattern = re.compile(blacklist_pattern)
        self.blacklist_pattern = blacklist_pattern
        self.excluded_events_index = excluded_events_index
        self.remove_files_when_done = remove_files_when_done
        self.sourcetype = sourcetype
        self.index = index

    def _teardown(self):
        self.session_key = None
        self.datainput = None
        self.aws_account = None
        self.message_id = None
        self.message = None
        self.blacklist_pattern = None
        self.excluded_events_index = None
        self.remove_files_when_done = None

    @staticmethod
    def validate(message):
        """
        Determine if given message conforms to this message type.

        :param message:
        :return:
        :rtype: bool
        """
        raise NotImplementedError()

    @staticmethod
    def description():
        """
        Description for this message type.

        :return:
        :rtype: basestring
        """
        raise NotImplementedError()

    def _s3_keys(self):
        """
        Get S3 Bucket and Key Names.

        :return: [(bucket_name, key_name), ...]
        :rtype: list
        """
        raise NotImplementedError()


class CloudTrailMessage(MessageProcessor):
    """
    CloudTrail Message.
    """

    REQUIRED_FIELDS = ('s3Bucket', 's3ObjectKey')

    @staticmethod
    def validate(message):
        """
        It has these keys: "s3Bucket", "s3ObjectKey".

        :param message:
        :return:
        """
        return all(f in message for f in CloudTrailMessage.REQUIRED_FIELDS) \
               and isinstance(message.get('s3ObjectKey'), (list,))  # validates s3ObjectKey is list

    @staticmethod
    def description():
        return 'CloudTrail Message'

    def _s3_keys(self):
        bucket_name = self.message['s3Bucket']
        for key_name in self.message.get('s3ObjectKey', []):
            yield bucket_name, key_name


class S3Message(MessageProcessor):
    """
    S3 Message.
    """

    RECORD_FIELDS = ('s3', 'eventName')

    @staticmethod
    def validate(message):
        """
        1. It has key "Records".
        2. The value of "Records" is a non-empty list.
        3. Elements of the list have key "s3" and "eventName".

        :param message:
        :return:
        """
        try:
            rec = message['Records'][0]
            return all(f in rec for f in S3Message.RECORD_FIELDS)
        except Exception:
            return False

    @staticmethod
    def description():
        return 'CloudTrail Message from S3 Bucket'

    def _s3_keys(self):
        for rec in self.message['Records']:
            try:
                bucket_name = rec['s3']['bucket']['name']
                key_name = rec['s3']['object']['key']
            except KeyError:
                logger.info('Invalid S3 notification record',
                            datainput=self.datainput,
                            message_id=self.message_id)
                continue
            yield bucket_name, key_name
