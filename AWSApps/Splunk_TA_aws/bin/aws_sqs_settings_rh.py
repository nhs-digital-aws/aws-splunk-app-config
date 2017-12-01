import aws_bootstrap_env

import splunk.admin as admin
from splunktalib.rest_manager import multimodel
import aws_settings_base_rh


class SQSLogging(aws_settings_base_rh.AWSLogging):
    keyMap = {
        'level': 'log_level'
    }


class SQSSettings(multimodel.MultiModel):
    endpoint = "configs/conf-aws_sqs"
    modelMap = {
        'logging': SQSLogging,
    }


if __name__ == "__main__":
    admin.init(
        multimodel.ResourceHandler(SQSSettings),
        admin.CONTEXT_APP_AND_USER,
    )
