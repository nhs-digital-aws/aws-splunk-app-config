"""
Custom REST Endpoint for enumerating AWS SQS queue names.
"""

import aws_bootstrap_env

import splunk
import splunk.admin
from aws_sqs_queue_urls_rh import SQSQueueURLsHandler
import splunk_ta_aws.common.ta_aws_common as tacommon
import splunk_ta_aws.common.proxy_conf as pc


class SQSQueueNamesHandler(SQSQueueURLsHandler):
    def handleList(self, confInfo):
        # Set proxy for boto3
        proxy = pc.get_proxy_info(self.getSessionKey())
        tacommon.set_proxy_env(proxy)
        queue_names = map(
            lambda queue_url: queue_url.split('/')[-1],
            self._list_queues(),
        )
        for queue in queue_names:
            confInfo[queue].append('sqs_queue', queue)


def main():
    splunk.admin.init(SQSQueueNamesHandler, splunk.admin.CONTEXT_NONE)


if __name__ == '__main__':
    main()
