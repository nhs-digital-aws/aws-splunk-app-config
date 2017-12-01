"""
Custom REST Endpoint for enumerating AWS regions.
"""

import aws_bootstrap_env

import splunk
import splunk.admin
from splunksdc import log as logging
from splunktaucclib.rest_handler.error import RestError
import splunk_ta_aws.common.ta_aws_consts as tac
import splunk_ta_aws.common.ta_aws_common as tacommon
from solnlib.splunkenv import get_splunkd_uri

logger = logging.get_module_logger()


# Copied from botocore endpoints.json
REGIONS = {
    "ap-northeast-1": {
        "description": "Asia Pacific (Tokyo)",
        "category": tac.RegionCategory.COMMERCIAL
    },
    "ap-northeast-2": {
        "description": "Asia Pacific (Seoul)",
        "category": tac.RegionCategory.COMMERCIAL
    },
    "ap-south-1": {
        "description": "Asia Pacific (Mumbai)",
        "category": tac.RegionCategory.COMMERCIAL
    },
    "ap-southeast-1": {
        "description": "Asia Pacific (Singapore)",
        "category": tac.RegionCategory.COMMERCIAL
    },
    "ap-southeast-2": {
        "description": "Asia Pacific (Sydney)",
        "category": tac.RegionCategory.COMMERCIAL
    },
    "ca-central-1": {
        "description": "Canada (Central)",
        "category": tac.RegionCategory.COMMERCIAL
    },
    "eu-central-1": {
        "description": "EU (Frankfurt)",
        "category": tac.RegionCategory.COMMERCIAL
    },
    "eu-west-1": {
        "description": "EU (Ireland)",
        "category": tac.RegionCategory.COMMERCIAL
    },
    "eu-west-2": {
        "description": "EU (London)",
        "category": tac.RegionCategory.COMMERCIAL
    },
    "sa-east-1": {
        "description": "South America (Sao Paulo)",
        "category": tac.RegionCategory.COMMERCIAL
    },
    "us-east-1": {
        "description": "US East (N. Virginia)",
        "category": tac.RegionCategory.COMMERCIAL
    },
    "us-east-2": {
        "description": "US East (Ohio)",
        "category": tac.RegionCategory.COMMERCIAL
    },
    "us-west-1": {
        "description": "US West (N. California)",
        "category": tac.RegionCategory.COMMERCIAL
    },
    "us-west-2": {
        "description": "US West (Oregon)",
        "category": tac.RegionCategory.COMMERCIAL
    },
    "us-gov-west-1": {
        "description": "AWS GovCloud (US)",
        "category": tac.RegionCategory.USGOV
    },
    "cn-north-1": {
        "description": "China (Beijing)",
        "category": tac.RegionCategory.CHINA
    }
}

ACCOUNT_OPT_ARGS = ['account', 'aws_account']


class DummyRegion(object):
    def __init__(self, name):
        self.name = name

    @staticmethod
    def from_names(names):
        return [DummyRegion(name) for name in names]


class ConfigHandler(splunk.admin.MConfigHandler):

    def setup(self):
        self.supportedArgs.addReqArg('aws_service')
        for account_arg in ACCOUNT_OPT_ARGS:
            self.supportedArgs.addOptArg(account_arg)

    def handleList(self, confInfo):
        service = self.callerArgs.data['aws_service'][0]

        account_category = None
        for account_arg in ACCOUNT_OPT_ARGS:
            if account_arg in self.callerArgs.data:
                account_name = self.callerArgs.data[account_arg][0]
                account = tacommon.get_account(get_splunkd_uri(), self.getSessionKey(), account_name)
                account_category = account.category
                break

        if service == 'aws_cloudwatch':
            import boto.ec2.cloudwatch
            regions = boto.ec2.cloudwatch.regions()
        elif service == 'aws_cloudtrail':
            import boto.cloudtrail
            regions = boto.cloudtrail.regions()
        elif service == 'aws_config':
            import boto.sqs
            regions = boto.sqs.regions()
        elif service == 'aws_config_rule':
            import boto.configservice
            # FIXME, hard code for now
            regions = DummyRegion.from_names([
                'us-east-1',
                'us-east-2',
                'us-west-1',
                'us-west-2',
                'ap-southeast-1',
                'ap-southeast-2',
                'ap-northeast-1',
                'ap-northeast-2',
                'eu-central-1',
                'eu-west-1',
            ])
        elif service == 'aws_cloudwatch_logs':
            import boto.logs
            regions = boto.logs.regions()
        elif service == 'aws_description':
            import boto.ec2
            regions = boto.ec2.regions()
        elif service == 'aws_inspector':
            regions = DummyRegion.from_names([
                'us-east-1',
                'us-west-2',
                'ap-northeast-2',
                'ap-south-1',
                'ap-southeast-2',
                'ap-northeast-1',
                'eu-west-1',
            ])
        elif service == 'aws_kinesis':
            import boto.kinesis
            regions = boto.kinesis.regions()
        elif service == 'aws_sqs_based_s3' or service == 'splunk_ta_aws_sqs':
            import boto.sqs
            regions = boto.sqs.regions()
        elif service == 'aws_s3':
            import boto.s3
            regions = boto.s3.regions()
        else:
            msg = "Unsupported aws_service={} specified.".format(service)
            raise RestError(400, msg)

        for r in regions:
            if account_category is None or REGIONS[r.name]['category'] == account_category:
                confInfo[r.name].append('label', REGIONS[r.name]['description'])

        if len(confInfo) == 0:
            raise RestError(400, 'This service is not available for your AWS account.')

def main():
    splunk.admin.init(ConfigHandler, splunk.admin.CONTEXT_NONE)


if __name__ == '__main__':
    main()
