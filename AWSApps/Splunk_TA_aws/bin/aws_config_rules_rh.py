import aws_bootstrap_env

import splunk.admin as admin

from splunktaucclib.rest_handler.error import RestError
from splunksdc import log as logging
import splunk_ta_aws.common.ta_aws_consts as tac
import splunktalib.common.pattern as scp
import splunk_ta_aws.common.ta_aws_common as tacommon
import splunk_ta_aws.common.proxy_conf as pc
from splunklib.client import Service
from splunksdc.config import ConfigManager
from solnlib.splunkenv import get_splunkd_access_info
from splunk_ta_aws.common.credentials import (
    AWSCredentialsProviderFactory,
    AWSCredentialsCache,
)


logger = logging.get_module_logger()


class ConfigRules(admin.MConfigHandler):
    valid_params = [tac.aws_region, tac.aws_account]
    optional_params = [tac.aws_iam_role]

    def setup(self):
        for param in self.valid_params:
            self.supportedArgs.addOptArg(param)
        for param in self.optional_params:
            self.supportedArgs.addOptArg(param)

    @scp.catch_all(logger)
    def handleList(self, conf_info):
        logger.info("start listing config rules")
        for required in self.valid_params:
            if not self.callerArgs or not self.callerArgs.get(required):
                logger.error('Missing "%s"', required)
                raise Exception('Missing "{}"'.format(required))

        # Set proxy for boto3
        proxy = pc.get_proxy_info(self.getSessionKey())
        tacommon.set_proxy_env(proxy)

        self._list_rules(conf_info)
        logger.info("end of listing config rules")

    def _list_rules(self, conf_info):
        aws_account = self.callerArgs.data['aws_account'][0]
        aws_iam_role = self.callerArgs.data.get('aws_iam_role', [None])[0]
        region_name = self.callerArgs.data['aws_region'][0]

        scheme, host, port = get_splunkd_access_info()
        service = Service(scheme=scheme, host=host, port=port,
                          token=self.getSessionKey())
        config = ConfigManager(service)
        factory = AWSCredentialsProviderFactory(config)
        provider = factory.create(aws_account, aws_iam_role)
        credentials_cache = AWSCredentialsCache(provider)
        client = credentials_cache.client('config', region_name)
        all_rules = []
        next_token = ""
        while 1:
            try:
                response = client.describe_config_rules(NextToken=next_token)
            except Exception as e:
                logger.error('Failed to describe config rules')
                msg = str(e.message)
                logger.error(msg)
                raise RestError(400, 'Failed to describe config rules: ' + msg)

            if not tacommon.is_http_ok(response):
                logger.error("Failed to describe config rules, errorcode=%s",
                             tacommon.http_code(response))
                return

            rules = response.get("ConfigRules")
            if not rules:
                break

            all_rules.extend(rule["ConfigRuleName"] for rule in rules)

            next_token = response.get("NextToken")
            if not next_token:
                break

        for rule in all_rules:
            conf_info[rule].append("rule_names", rule)


def main():
    admin.init(ConfigRules, admin.CONTEXT_NONE)


if __name__ == "__main__":
    main()
