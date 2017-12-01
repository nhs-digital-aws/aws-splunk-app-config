"""
Custom REST Endpoint for enumerating AWS cloudwatch namepaces.
"""

import aws_bootstrap_env

import splunk
import splunk.admin
from splunksdc import log as logging
from splunk_ta_aws.common import s3util
import splunk_ta_aws.common.ta_aws_common as tacommon


logger = logging.get_module_logger()


class ConfigHandler(splunk.admin.MConfigHandler):

    def setup(self):
        self.supportedArgs.addReqArg('aws_region')
        self.supportedArgs.addReqArg('aws_account')

    def handleList(self, confInfo):
        try:
            key_id, secret_key = tacommon.assert_creds(
                self.callerArgs["aws_account"][0], self.getSessionKey(), logger)
            namespaces = s3util.list_cloudwatch_namespaces(
                self.callerArgs['aws_region'][0], key_id, secret_key,
                self.getSessionKey())
            confInfo['NameSpacesResult'].append('metric_namespace', namespaces)
        except Exception, exc:
            err = "Error while loading Metric Namespace: type=%s, content=%s" \
                  "" % (type(exc), exc)
            print err
            raise BaseException()


def main():
    splunk.admin.init(ConfigHandler, splunk.admin.CONTEXT_NONE)


if __name__ == '__main__':
    main()
