import aws_bootstrap_env

import splunk.admin as admin
from splunktalib.rest_manager import multimodel
import aws_settings_base_rh


class KinesisLogging(aws_settings_base_rh.AWSLogging):
    keyMap = {
        'level': 'log_level'
    }


class KinesisSettings(multimodel.MultiModel):
    endpoint = "configs/conf-aws_kinesis"
    modelMap = {
        'logging': KinesisLogging,
    }


if __name__ == "__main__":
    admin.init(multimodel.ResourceHandler(KinesisSettings), admin.CONTEXT_APP_AND_USER)
