import json
import types
import copy
import datetime
import time

import splunk_ta_aws.common.ta_aws_consts as tac
from splunk_ta_aws.common.ta_aws_common import load_credentials_from_cache

import splunksdc.log as logging
from botocore.exceptions import ClientError
from boto.exception import BotoServerError


logger = logging.get_module_logger()


_BUILT_IN_TYPES = (
    types.NoneType,
    types.BooleanType,
    types.IntType,
    types.LongType,
    types.FloatType,
    types.StringType,
    types.UnicodeType,
    types.ListType,
    types.DictType,
)

DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S.%f'

OP_WHITELIST = ['describe_', 'get_', 'list_']
OP_BLACKLIST = []
REQUEST_LIMIT_ERROR_CODE = 'RequestLimitExceeded'


class _ExtendedEncoder(json.JSONEncoder):
    def default(self, obj):
        # check datetime
        if isinstance(obj, datetime.datetime):
            # ISO 8601 time format
            if obj.utcoffset() is None or obj.utcoffset().total_seconds() == 0:
                return obj.strftime(DATETIME_FORMAT)[:-3] + 'Z'
            else:
                return obj.strftime(DATETIME_FORMAT)[:-3] + obj.strftime('%z')

        if not isinstance(obj, _BUILT_IN_TYPES):
            return str(obj)

        return json.JSONEncoder.default(self, obj)


class BotoRetryWrapper(object):
    def __init__(self, boto_client = None, retries = 5):
        self.boto_client = boto_client
        self.retries = retries

    def __getattr__(self, item):
        need_retry = False

        for op in OP_WHITELIST:
            if item.startswith(op):
                need_retry = True
                break

        for op in OP_BLACKLIST:
            if item.startswith(op):
                need_retry = False
                break

        if not need_retry:
            return getattr(self.boto_client, item)

        def wrapper_func(*args, **kwargs):
            max_tries = max(self.retries, 0) + 1
            last_ex = None

            for i in xrange(max_tries):
                try:
                    return getattr(self.boto_client, item)(*args, **kwargs)

                except Exception as e:
                    error_code = None

                    if isinstance(e, ClientError):
                        if 'Code' in e.response['Error']:
                            error_code = e.response['Error']['Code']
                    elif isinstance(e, BotoServerError):
                        error_code = e.error_code

                    if error_code == REQUEST_LIMIT_ERROR_CODE:
                        last_ex = e
                        if i < max_tries - 1:
                            time.sleep(2 ** i)
                        logger.warn('Retry description function (%s).' % item)
                        continue
                    elif error_code and (error_code.startswith('NoSuch') or error_code == 'InvalidAction'):
                        # these exceptions need not error logs
                        raise
                    else:
                        logger.exception('Run description function (%s) failed.' % item)
                        raise

            if last_ex:
                logger.exception('Run description function (%s) failed after retries.' % item)
                raise last_ex

        return wrapper_func


def serialize(value):
    return json.dumps(value, cls=_ExtendedEncoder)


def pop_description_result(item, keys, init_result,
                           pop_region_name=True, raw_event=False):
    if item is None:
        return {}

    result = dict(init_result)
    if pop_region_name:
        try:
            region_name = item.region.name  # item.region is an object
        except Exception:
            region_name = None
        result[tac.region] = region_name

    for key in keys:
        result[key] = item.get(key) if isinstance(item, types.DictType) else getattr(item, key, None)

    if not raw_event:
        result = json.dumps(result, cls=_ExtendedEncoder)

    return result


def pop_description_results(items, keys, init_result,
                            pop_region_name=True, raw_event=False):
    results = []
    if not items:
        return results

    for item in items:
        if item is None:
            continue

        result = pop_description_result(
            item, keys, init_result, pop_region_name, raw_event)

        results.append(result)
    return results


def refresh_credentials(func):
    """
    Decorator for refreshing credentials.

    :param func:
    :return:
    """

    def load_credentials(config):
        credentials = load_credentials_from_cache(
            config[tac.server_uri],
            config[tac.session_key],
            config[tac.aws_account],
            config.get(tac.aws_iam_role),
        )
        config[tac.key_id] = credentials.aws_access_key_id
        config[tac.secret_key] = credentials.aws_secret_access_key
        config['aws_session_token'] = credentials.aws_session_token
        config[tac.account_id] = credentials.account_id

    def wrapper(config, *args, **kwargs):
        load_credentials(config)
        return func(config, *args, **kwargs)

    return wrapper


def describe_pagination(func):
    """
    Describe all metadata which based on pagination.

    :return:
    """

    def wrapper(*args, **kwargs):
        pagination = {}
        ret_all = []
        while True:
            kwargs_new = copy.copy(kwargs)
            kwargs_new.update(pagination)
            ret, pagination = func(*args, **kwargs_new)
            ret_all.extend(ret)
            pagination = {key: val for key, val in pagination.iteritems()
                          if val is not None}
            if not pagination:
                break
        return ret_all

    return wrapper
