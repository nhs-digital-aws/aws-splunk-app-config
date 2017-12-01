import json

import boto3

import splunksdc.log as logging

from splunk_ta_aws.common.ta_aws_common import is_http_ok
import splunk_ta_aws.common.ta_aws_consts as tac
import description as desc

logger = logging.get_module_logger()


def get_lambda_client(config):
    return desc.BotoRetryWrapper(boto_client=boto3.client(
        'lambda',
        region_name=config[tac.region],
        aws_access_key_id=config[tac.key_id],
        aws_secret_access_key=config[tac.secret_key],
        aws_session_token=config.get('aws_session_token')
    ))


@desc.refresh_credentials  # Already pagination inside
def lambda_functions(config):
    client = get_lambda_client(config)
    params = {'MaxItems': 1000}
    while True:
        resp = client.list_functions(**params)
        if not is_http_ok(resp):
            logger.error('Fetch Lambda functions failed',
                         response=resp.get('Failed', resp))
        for func in resp.get('Functions', []):
            func[tac.region] = config[tac.region]
            yield json.dumps(func)
        try:
            params['Marker'] = resp['NextMarker']
        except Exception:
            break
