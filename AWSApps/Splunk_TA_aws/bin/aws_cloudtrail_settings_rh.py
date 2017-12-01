import aws_bootstrap_env

import splunk.admin as admin

from splunktalib.rest_manager import multimodel

import aws_settings_base_rh

class CloudTrailLogging(aws_settings_base_rh.AWSLogging):
    keyMap = {
        'level': 'log_level'
    }


class CloudTrailSettings(multimodel.MultiModel):
    endpoint = "configs/conf-aws_cloudtrail"
    modelMap = {
        'logging': CloudTrailLogging,
    }


if __name__ == "__main__":
    admin.init(multimodel.ResourceHandler(CloudTrailSettings), admin.CONTEXT_APP_AND_USER)
