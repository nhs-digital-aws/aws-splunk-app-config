import aws_bootstrap_env

import splunk.admin as admin
from splunktalib.rest_manager import multimodel
import aws_settings_base_rh


class AWSLogsSettings(aws_settings_base_rh.AWSLogging):
    keyMap = {
        'level': 'log_level'
    }


class S3IncrementalSettings(multimodel.MultiModel):
    endpoint = 'configs/conf-aws_settings'
    modelMap = {
        'splunk_ta_aws_logs': AWSLogsSettings,
    }


if __name__ == '__main__':
    admin.init(
        multimodel.ResourceHandler(S3IncrementalSettings),
        admin.CONTEXT_APP_AND_USER,
    )