import re
from splunksdc import log as logging

logger = logging.get_module_logger()


_MAX_WAIT_TIME_SECONDS = 20


class SQSMessage(object):
    def __init__(self, message):
        self._message = message
        self._attributes = message['Attributes']

    @property
    def message_id(self):
        return self._message['MessageId']

    @property
    def receipt_handle(self):
        return self._message['ReceiptHandle']

    @property
    def md5_of_body(self):
        return self._message['MD5OfBody']

    @property
    def body(self):
        return self._message['Body']

    @property
    def first_receive_timestamp(self):
        return self._attributes['ApproximateFirstReceiveTimestamp']

    @property
    def receive_count(self):
        return self._attributes['ApproximateReceiveCount']

    @property
    def sender_id(self):
        return self._attributes['SenderId']

    @property
    def sent_timestamp(self):
        return self._attributes['SentTimestamp']


class QueueAttributes(object):
    def __init__(self, attributes):
        self._attributes = attributes

    def _get(self, name):
        return self._attributes.get(name)

    @property
    def visibility_timeout(self):
        return int(self._get('VisibilityTimeout'))

    @property
    def redrive_policy(self):
        return self._get('RedrivePolicy')


def query_url_by_name(client, name):
    params = {
        'QueueName': name,
    }
    logger.debug('SQSGetQueueURL', **params)
    response = client.get_queue_url(**params)
    return response.get('QueueUrl')


class SQSQueue(object):
    _PATTERN = re.compile(r'//sqs\.(?P<region>[-\w]+)\.amazonaws\.')

    @classmethod
    def _extract_region(cls, url, default):
        match = cls._PATTERN.search(url)
        if not match:
            return default
        return match.group('region')

    def __init__(self, url, region):
        """
        :param url: The URL of queue
        """
        self._url = url
        self._region = self._extract_region(url, region)

    def get_messages(self, client, batch_size):
        """
        :param client: sqs service client
        :param batch_size: The max number of messages would be received in one request
        :return: collection of SQSMessage
        """
        url = self._url
        params = {
            'QueueUrl': url,
            'MaxNumberOfMessages': batch_size,
            'WaitTimeSeconds': _MAX_WAIT_TIME_SECONDS,
            'AttributeNames': ['All']
        }
        logger.debug('Get SQS messages', **params)
        response = client.receive_message(**params)
        messages = response.get('Messages', [])
        if messages:
            logger.debug('Messages received.', count=len(messages))
            return [SQSMessage(message) for message in messages]
        logger.debug('No message available.')
        return []

    def delete_message(self, client, message):
        """
        :param client: sqs service client
        :param message: an instance of SQSMessage
        """
        url = self._url
        params = {
            'QueueUrl': url,
            'ReceiptHandle': message.receipt_handle,
        }
        logger.debug('Delete SQS message', **params)
        client.delete_message(**params)
        return

    def get_attributes(self, client):
        url = self._url
        params = {
            'QueueUrl': url,
            'AttributeNames': ['All']
        }
        response = client.get_queue_attributes(**params)
        return QueueAttributes(response['Attributes'])

    def client(self, credentials, session=None):
        return credentials.client('sqs', self._region, session)

