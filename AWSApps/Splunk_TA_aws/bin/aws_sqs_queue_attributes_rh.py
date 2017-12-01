import aws_bootstrap_env

import splunk
import splunk.admin
from botocore.exceptions import ClientError
from splunktalib.rest_manager.error_ctl import RestHandlerError

from splunklib.client import Service
from splunksdc.config import ConfigManager
from solnlib.splunkenv import get_splunkd_access_info
from splunk_ta_aws.common.sqs import SQSQueue
from splunk_ta_aws.common.credentials import (
    AWSCredentialsProviderFactory,
    AWSCredentialsCache,
)
import splunk_ta_aws.common.ta_aws_common as tacommon
import splunk_ta_aws.common.proxy_conf as pc


def query_queue_attributes(
        session_key,
        aws_account,
        aws_iam_role,
        region_name,
        sqs_queue_url,
):
    scheme, host, port = get_splunkd_access_info()
    service = Service(scheme=scheme, host=host, port=port, token=session_key)
    config = ConfigManager(service)
    factory = AWSCredentialsProviderFactory(config)
    provider = factory.create(aws_account, aws_iam_role)
    credentials_cache = AWSCredentialsCache(provider)
    client = credentials_cache.client('sqs', region_name)
    queue = SQSQueue(sqs_queue_url, region_name)
    return queue.get_attributes(client)


class SqsQueueAtrributesHandler(splunk.admin.MConfigHandler):

    def setup(self):
        self.supportedArgs.addReqArg('aws_account')
        self.supportedArgs.addOptArg('aws_iam_role')
        self.supportedArgs.addReqArg('aws_region')
        self.supportedArgs.addReqArg('sqs_queue_url')

    def handleList(self, confInfo):
        # Set proxy for boto3
        proxy = pc.get_proxy_info(self.getSessionKey())
        tacommon.set_proxy_env(proxy)

        try:
            attrs = query_queue_attributes(
                self.getSessionKey(),
                self.callerArgs.data['aws_account'][0],
                self.callerArgs.data.get('aws_iam_role', [None])[0],
                self.callerArgs.data['aws_region'][0],
                self.callerArgs.data['sqs_queue_url'][0],
            )
        except ClientError as exc:
            RestHandlerError.ctl(400, msgx=exc)
            return
        confInfo['Attributes']['VisibilityTimeout'] = attrs.visibility_timeout
        confInfo['Attributes']['RedrivePolicy'] = attrs.redrive_policy


def main():
    splunk.admin.init(SqsQueueAtrributesHandler, splunk.admin.CONTEXT_NONE)


if __name__ == '__main__':
    main()
