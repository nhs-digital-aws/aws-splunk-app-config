import aws_bootstrap_env
import os
import sys
import re


import splunk.admin as admin

from splunktalib.rest_manager import multimodel

import aws_settings_base_rh


class CloudWatchLogsLogging(aws_settings_base_rh.AWSLogging):
    keyMap          = {
                      'level': 'log_level'
                      }


class CloudWatchLogsSettings(multimodel.MultiModel):
    endpoint    = "configs/conf-aws_cloudwatch_logs"
    modelMap    = {
                  'logging': CloudWatchLogsLogging,
                  }


if __name__ == "__main__":
    admin.init(multimodel.ResourceHandler(CloudWatchLogsSettings), admin.CONTEXT_APP_AND_USER)
