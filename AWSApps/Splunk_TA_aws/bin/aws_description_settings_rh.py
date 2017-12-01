import aws_bootstrap_env

import splunk.admin as admin

from splunktalib.rest_manager import multimodel

import aws_settings_base_rh


class DescriptionLogging(aws_settings_base_rh.AWSLogging):
    keyMap = {
        "level": "log_level"
    }


class DescriptionSettings(multimodel.MultiModel):
    endpoint = "configs/conf-aws_description"
    modelMap = {
        "logging": DescriptionLogging,
    }


if __name__ == "__main__":
    admin.init(multimodel.ResourceHandler(DescriptionSettings),
               admin.CONTEXT_APP_AND_USER)
