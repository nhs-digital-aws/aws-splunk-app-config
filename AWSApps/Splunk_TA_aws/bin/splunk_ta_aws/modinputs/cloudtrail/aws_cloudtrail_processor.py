import re
import logging
import traceback
from multiprocessing.dummy import Pool as ThreadPool

from splunktalib.common import util as scutil
from splunksdc import logging

from aws_cloudtrail_common import InputCancellationError
from aws_cloudtrail_notification import (
    NotificationProcessor,
    CloudTrailProcessorError,
)
from aws_cloudtrail_message import get_processor


logger = logging.get_module_logger()


class CloudTrailProcessor(object):
    """
    Processing AWS CloudTrail notifications from SQS.
    """

    TOTAL = 'total'
    FAILED = 'failed'
    SUCCESSFUL = 'successful'
    UNPROCESSED = 'unprocessed'

    def __init__(self, session_key, input_name, input_item, aws_account,
                 local_store, thread_count=32):
        self.session_key = session_key
        self.input_name = input_name
        self.input_item = input_item
        self.aws_account = aws_account
        self.local_store = local_store
        self._thread_count = thread_count

        try:
            self._parse()
        except Exception:
            logger.error('Invalid Input', datainput=self.input_name,
                         aws_account=self.input_item['aws_account'],
                         error=traceback.format_exc())
            raise

    def run(self):
        """
        Run Processing Messages.

        :return: failed count
        """
        pool = ThreadPool(self._thread_count)
        keys = self.local_store.range()
        total = len(keys)
        ret = {
            CloudTrailProcessor.TOTAL: total,
            CloudTrailProcessor.UNPROCESSED: 0,
            CloudTrailProcessor.SUCCESSFUL: 0,
            CloudTrailProcessor.FAILED: 0,
        }

        if not total:
            logger.debug('SQS is empty', datainput=self.input_name,
                         aws_region=self.input_item['aws_region'],
                         sqs_queue=self.input_item['sqs_queue'])
            return ret

        results = pool.map(self._process, keys)
        pool.close()
        pool.join()
        self.local_store.sweep()
        for res in results:
            ret[res] += 1
        return ret

    def _log(self, msg_cont, msg_id, level=logging.DEBUG, **kwargs):
        logger.log(level, msg_cont, datainput=self.input_name,
                   aws_account=self.input_item['aws_account'],
                   message_id=msg_id, **kwargs)

    def _process(self, msg_id):
        self._log('Processing Started', msg_id)
        msg_body = self.local_store.get(msg_id)
        logger.debug('Processing Message', datainput=self.input_name,
                     message=msg_body)
        try:
            msg = NotificationProcessor.load(msg_body)
            processor = get_processor(msg)
        except CloudTrailProcessorError:
            # Invalid message
            self.local_store.delete(msg_id)
            self._log(
                'Invalid message, delete it from ckpt',
                msg_id,
                level=logging.ERROR,
                error=traceback.format_exc(),
                message_body=msg_body,
            )
            return CloudTrailProcessor.FAILED

        try:
            processor.run(self.session_key, self.input_name,
                          self.aws_account, msg_id, msg,
                          self._blacklist_pattern, self._excluded_events_index,
                          self._remove_files_when_done,
                          self.input_item.get('sourcetype', 'aws:cloutrail'),
                          self.input_item.get('index', 'default'))
            self.local_store.delete(msg_id)
        except InputCancellationError:
            self._log('Orphan Process', msg_id)
            return CloudTrailProcessor.UNPROCESSED
        except Exception:
            self._log('Processing Failed', msg_id, level=logging.ERROR,
                      error=traceback.format_exc())
            return CloudTrailProcessor.FAILED
        else:
            self._log('Processing Finished', msg_id)
            return CloudTrailProcessor.SUCCESSFUL

    def _parse(self):
        self._remove_files_when_done = scutil.is_true(
            self.input_item.get('remove_files_when_done', '0'))
        self._exclude_describe_events = scutil.is_true(
            self.input_item.get('exclude_describe_events', '1'))
        blacklist = self.input_item.get('blacklist', '^(?:Describe|List|Get)')
        self._blacklist = blacklist \
            if (blacklist and self._exclude_describe_events) else None
        self._blacklist_pattern = re.compile(self._blacklist) \
            if self._blacklist is not None else None
        logger.debug('Blacklist for eventNames', datainput=self.input_name,
                     regex=self._blacklist or '')
        self._excluded_events_index = \
            self.input_item.get('excluded_events_index')
