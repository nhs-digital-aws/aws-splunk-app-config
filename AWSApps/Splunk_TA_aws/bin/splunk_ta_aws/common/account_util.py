import re
import boto3
from splunk_ta_aws.common.ta_aws_common import set_proxy_env
import splunk_ta_aws.common.proxy_conf as pc
import splunk_ta_aws.common.ta_aws_consts as tac
from botocore.exceptions import ClientError
import splunk.search as search

ACCOUNT_APPEND_SPL = '''
    | makeresults
    | eval account_id="%s", name="%s", category="%s"
    | table account_id, name, category
    | collect `aws-account-index`
'''


def get_account_id(account, session_key):
    # we can directly get account_id in EC2 Role
    if account.get('iam') and account.get('account_id'):
        return account.get('account_id')

    # Set proxy
    proxy = pc.get_proxy_info(session_key)
    set_proxy_env(proxy)

    # get arn
    arn = _get_caller_identity(account)['Arn']

    match_results = re.findall(r"^arn:aws(-\S+)?:iam::(\d+):", arn)

    if len(match_results) == 1:
        partition_name, account_id = match_results[0]
        return account_id

    return None


def validate_keys(session_key, **account_info):
    # Set proxy
    proxy = pc.get_proxy_info(session_key)
    set_proxy_env(proxy)

    try:
        _get_caller_identity(account_info)
    except ClientError as e:
        if e.response['Error']['Code'] == 'InvalidClientTokenId':
            return False

    return True


def append_account_to_summary(name=None, account_id=None, category=None, session_key=None):
    search.dispatch(ACCOUNT_APPEND_SPL % (account_id, name, category),
                    sessionKey=session_key)
    return


def append_assume_role_to_summary(name=None, arn=None, session_key=None):
    account_id = extract_account_id_from_role_arn(arn)

    if account_id:
        search.dispatch(ACCOUNT_APPEND_SPL % (account_id, name, 'N/A'),
                        sessionKey=session_key)

    return


def extract_account_id_from_role_arn(role_arn):
    pattern = re.compile('^arn:[^\s:]+:iam::(\d+):role')
    search_result = pattern.search(role_arn)

    if search_result:
        return search_result.groups()[0]

    return None

def _get_caller_identity(account):
    credentials = {}

    if account.get('key_id') is not None:
        credentials['aws_access_key_id'] = account['key_id']
    if account.get('secret_key') is not None:
        credentials['aws_secret_access_key'] = account['secret_key']
    if account.get('token') is not None:
        credentials['aws_session_token'] = account['token']
    if account.get('category') is not None:
        category = int(account.get('category'))
        if category == tac.RegionCategory.USGOV:
            region = 'us-gov-west-1'
            credentials['region_name'] = region
        elif category == tac.RegionCategory.CHINA:
            region = 'cn-north-1'
            credentials['region_name'] = region

    sts_client = boto3.client('sts', **credentials)
    return sts_client.get_caller_identity()