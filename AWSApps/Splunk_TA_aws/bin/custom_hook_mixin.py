import re
import os
import json

from splunktaucclib.rest_handler.error import RestError
from splunktaucclib.rest_handler.base_hook_mixin import BaseHookMixin
import splunk_ta_aws.common.ta_aws_consts as tac
import splunk_ta_aws.modinputs.generic_s3.aws_s3_consts as asc
from splunk_ta_aws.modinputs.generic_s3.aws_s3_common import get_region_for_bucketname
import splunk_ta_aws.common.ta_aws_common as tacommon
from solnlib.splunkenv import get_splunkd_uri
import splunksdc.log as logging
from botocore.regions import EndpointResolver
import splunk_ta_aws.common.proxy_conf as pc


logger = logging.get_module_logger()

ENDPOINTS_PATH = os.path.join(os.path.dirname(__file__), '3rdparty', 'botocore', 'data', 'endpoints.json')


class CustomHookMixin(BaseHookMixin):

    BUCKET_NAME_INPUTS = ['aws_billing', 'aws_s3', 'splunk_ta_aws_logs']

    def create_hook(self, session_key, config_name, stanza_id, payload):
        self._delete_ckpt(config_name, stanza_id)
        payload = self._fill_host_and_region(session_key, config_name, payload)

        return payload

    def delete_hook(self, session_key, config_name, stanza_id):
        self._delete_ckpt(config_name, stanza_id)
        return True

    def _fill_host_and_region(self, session_key, config_name, payload):
        if config_name in self.BUCKET_NAME_INPUTS:
            if asc.host_name in payload and len(payload[asc.host_name]) > 0:
                return payload

            (region, host) = self._get_region_host(session_key, payload)
            if config_name == 'splunk_ta_aws_logs':
                payload[asc.bucket_region] = region

            payload[asc.host_name] = host

        return payload

    def _get_region_host(self, session_key, payload):
        config = pc.get_proxy_info(session_key)
        tacommon.set_proxy_env(config)

        credentials_service = tacommon.create_credentials_service(
            get_splunkd_uri(), session_key)

        credentials = credentials_service.load(
            payload[tac.aws_account],
            payload[tac.aws_iam_role],
        )

        config[tac.key_id] = credentials.aws_access_key_id
        config[tac.secret_key] = credentials.aws_secret_access_key
        config['aws_session_token'] = credentials.aws_session_token
        config[asc.bucket_name] = payload[asc.bucket_name]
        config[asc.host_name] = tac.CATEGORY_HOST_NAME_MAP[credentials.category]

        if config[asc.host_name] == asc.default_host:
            region = get_region_for_bucketname(config)
            with open(ENDPOINTS_PATH, 'r') as endpoints_file:
                endpoints = json.load(endpoints_file)

            host_name = EndpointResolver(endpoints).construct_endpoint('s3', region).get('hostname', asc.default_host)
        else:
            pattern = r's3[.-]([\w-]+)\.amazonaws.com'
            m = re.search(pattern, config[asc.host_name])
            region = m.group(1) if m else 'us-east-1'
            host_name = config[asc.host_name]

        return (region, host_name)

    def _delete_ckpt(self, config_name, stanza_id):
        if config_name == 'aws_cloudtrail':
            try:
                from splunk_ta_aws.modinputs.cloudtrail import delete_ckpt
                delete_ckpt(stanza_id)
            except Exception as exc:
                if (isinstance(exc, IOError) and
                        'No such file or directory' in str(exc)):
                    return
                RestError(500, 'Failed to delete checkpoint')
        elif config_name == 'aws_s3':
            try:
                from splunk_ta_aws.modinputs.generic_s3 import delete_ckpt
                delete_ckpt(stanza_id)
            except Exception as exc:
                if (isinstance(exc, IOError) and
                        'No such file or directory' in str(exc)):
                    return
                RestError(500, 'Failed to delete checkpoint')
        elif config_name == 'splunk_ta_aws_logs':
            try:
                from splunk_ta_aws.modinputs.incremental_s3 import delete_data_input
                delete_data_input(stanza_id)
            except Exception as exc:
                if (isinstance(exc, IOError) and
                        'No such file or directory' in str(exc)):
                    return
                RestError(500, 'Failed to delete checkpoint')

        return True
