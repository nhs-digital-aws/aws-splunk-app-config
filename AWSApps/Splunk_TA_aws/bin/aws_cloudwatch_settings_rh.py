import aws_bootstrap_env

import splunk.admin as admin
from splunktalib.rest_manager import multimodel
import aws_settings_base_rh


class CloudWatchLogging(aws_settings_base_rh.AWSLogging):
    keyMap = {
        'level': 'log_level'
    }


class CloudWatchSettings(multimodel.MultiModel):
    endpoint = 'configs/conf-aws_cloudwatch'
    modelMap = {
        'logging': CloudWatchLogging,
    }


if __name__ == '__main__':
    admin.init(
        multimodel.ResourceHandler(CloudWatchSettings),
        admin.CONTEXT_APP_AND_USER,
    )
