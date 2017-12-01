"""
AWS SQS Queue Message Collecting.
Copied from the original SQS modinputs, because sqs now
changed to single thread and added assumerole.
"""

import json
import traceback
from multiprocessing.dummy import Pool as ThreadPool

import boto3

from splunktalib.common import util as scutil

from splunk_ta_aws.common.ta_aws_common import is_http_ok


def get_sqs_client(aws_region, key_id, secret_key, token=None):
    credentials = {'aws_session_token': token} if token else \
        {'aws_access_key_id': key_id, 'aws_secret_access_key': secret_key}
    return boto3.client(
        'sqs',
        region_name=aws_region,
        **credentials
    )


def get_sqs_queue_url(client, queue_name):
    """
    Get SQS queue url for given SQS client and queue name.

    :param client:
    :param queue_name:
    :return:
    """
    return client.get_queue_url(QueueName=queue_name).get('QueueUrl')


def check_sqs_response(content):
    """
    Check if it is successful while acting on SQS queue.
    :param content: acting response
    :return:
    """
    if not is_http_ok(content):
        err = json.dumps(content.get('Failed') or content)
        raise SQSCollectorException(err)


class SQSCollectorException(Exception):
    """
    Exception for SQS handler.
    """
    pass


class SQSCollector(object):

    def __init__(self, client, queue_url, logger, handler,
                 thread_count=8, *args, **kwargs):
        """

        :param client:
        :param queue_url:
        :param logger:
        :param handler: handler to process message from SQS queue.
            It should be in form:
                def handler(messages, *args, **kwargs): ...
        :param thread_count:
        :param args: args for handler
        :param kwargs: kwargs for handler
        """
        self._client = client
        self._queue_url = queue_url
        self._logger = logger
        self._thread_count = thread_count

        assert callable(handler), '"handler" must be callable'
        self._handler = handler
        self._handler_args = args
        self._handler_kwargs = kwargs

    def run(self):
        """
        Run collecting.

        :return:
        """
        pool = ThreadPool(self._thread_count)
        results = pool.map(lambda f: f(), [self._collect]*self._thread_count)
        pool.close()
        pool.join()
        return True in results

    @scutil.retry(retries=3, reraise=True, logger=None)
    def receive_messages(self):
        resp = self._client.receive_message(
            QueueUrl=self._queue_url,
            AttributeNames=['All'],
            MessageAttributeNames=['All'],
            MaxNumberOfMessages=10,
            VisibilityTimeout=120,
            WaitTimeSeconds=2,
        )
        check_sqs_response(resp)
        return resp.get('Messages')

    @scutil.retry(retries=3, reraise=True, logger=None)
    def delete_messages(self, messages):
        ents = [
            {'Id': msg['MessageId'], 'ReceiptHandle': msg['ReceiptHandle']}
            for msg in messages
        ]
        resp = self._client.delete_message_batch(
            QueueUrl=self._queue_url,
            Entries=ents,
        )
        check_sqs_response(resp)

    def _collect(self):
        msg_count = 0
        try:
            while True:
                msgs = self.receive_messages()
                # If it is None, queue is empty
                if msgs is None:
                    break

                msg_count += len(msgs)
                self._handler(msgs, *self._handler_args, **self._handler_kwargs)
                self.delete_messages(msgs)
            self._logger.info('Pulled %d messages from SQS', msg_count)
        except Exception as e:
            self._logger.error(
                'Ingest SQS Failed',
                queue_url=self._queue_url,
                error=traceback.format_exc(),
            )
            return False
        else:
            return True