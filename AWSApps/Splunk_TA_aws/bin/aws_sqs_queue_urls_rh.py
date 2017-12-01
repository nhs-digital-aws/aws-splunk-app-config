"""
Custom REST Endpoint for enumerating AWS SQS queue names.
"""
import aws_bootstrap_env

import splunk
import splunk.admin
from botocore.exceptions import ClientError
from splunktalib.rest_manager.error_ctl import RestHandlerError
from splunklib.client import Service
from splunksdc.config import ConfigManager
from solnlib.splunkenv import get_splunkd_access_info
from splunk_ta_aws.common.credentials import (
    AWSCredentialsProviderFactory,
    AWSCredentialsCache,
)
import splunk_ta_aws.common.ta_aws_common as tacommon
import splunk_ta_aws.common.proxy_conf as pc


class SQSQueueURLsHandler(splunk.admin.MConfigHandler):

    def setup(self):
        self.supportedArgs.addReqArg('aws_region')
        self.supportedArgs.addOptArg('aws_iam_role')
        self.supportedArgs.addReqArg('aws_account')

    def handleList(self, confInfo):
        # Set proxy for boto3
        proxy = pc.get_proxy_info(self.getSessionKey())
        tacommon.set_proxy_env(proxy)

        for queue_url in self._list_queues():
            confInfo[queue_url].append('label', queue_url.split('/')[-1])

    def _list_queues(self):
        aws_account = self.callerArgs.data['aws_account'][0]
        aws_iam_role = self.callerArgs.data.get('aws_iam_role', [None])[0]
        region_name = self.callerArgs.data['aws_region'][0]

        scheme, host, port = get_splunkd_access_info()
        service = Service(scheme=scheme, host=host, port=port,
                          token=self.getSessionKey())
        config = ConfigManager(service)
        factory = AWSCredentialsProviderFactory(config)
        provider = factory.create(aws_account, aws_iam_role)
        credentials_cache = AWSCredentialsCache(provider)
        client = credentials_cache.client('sqs', region_name)
        try:
            queues = client.list_queues()
            if 'QueueUrls' in queues:
                return queues['QueueUrls']
            else:
                return []
        except ClientError as exc:
            RestHandlerError.ctl(400, msgx=exc)


def main():
    splunk.admin.init(SQSQueueURLsHandler, splunk.admin.CONTEXT_NONE)


if __name__ == '__main__':
    main()
