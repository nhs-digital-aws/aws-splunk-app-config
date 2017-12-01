import aws_bootstrap_env

import splunk.admin as admin

from splunktalib.rest_manager import multimodel

import aws_settings_base_rh


class SQSBasedS3Logging(aws_settings_base_rh.AWSLogging):
    keyMap = {
        'level': 'log_level'
    }


class SQSBasedS3Settings(multimodel.MultiModel):
    endpoint = 'configs/conf-aws_settings'
    modelMap = {
        'logging': SQSBasedS3Logging,
    }


class SQSBasedS3SettingsHandler(aws_settings_base_rh.AWSSettingHandler):
    stanzaName = 'aws_sqs_based_s3'

if __name__ == '__main__':
    admin.init(
        multimodel.ResourceHandler(SQSBasedS3Settings, SQSBasedS3SettingsHandler),
        admin.CONTEXT_APP_AND_USER,
    )
