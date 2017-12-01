import os
import re
import codecs
from datetime import datetime

from dateutil.parser import parse as parse_timestamp

import boto
import boto.s3 as bs
import boto.s3.connection as bsc
from splunk_ta_aws.common import boto2_s3_patch

import splunk_ta_aws.common.ta_aws_consts as tac
import aws_s3_consts as asc
import splunksdc.log as logging
from boto.compat import unquote_str
from solnlib.utils import retry


logger = logging.get_module_logger()


sourcetype_to_keyname_regex = {
    asc.aws_cloudtrail: r"\d+_CloudTrail_[\w-]+_\d{4}\d{2}\d{2}T\d{2}\d{2}Z_.{16}\.json\.gz$",
    asc.aws_elb_accesslogs: r".*\d+_elasticloadbalancing_[\w-]+_.+\.log(\.gz)?$",
    asc.aws_cloudfront_accesslogs: r".+\.\d{4}-\d{2}-\d{2}-\d{2}\..+\.gz$",
    asc.aws_s3_accesslogs: r".+\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}-.+$"
}


def _create_s3_connection(config, region):
    calling_format = bsc.OrdinaryCallingFormat()
    if region:
        conn = bs.connect_to_region(
            region,
            aws_access_key_id=config[tac.key_id],
            aws_secret_access_key=config[tac.secret_key],
            security_token=config.get('aws_session_token'),
            proxy=config.get(tac.proxy_hostname),
            proxy_port=config.get(tac.proxy_port),
            proxy_user=config.get(tac.proxy_username),
            proxy_pass=config.get(tac.proxy_password),
            is_secure=True,
            validate_certs=True,
            calling_format=calling_format)
    else:
        if (not os.environ.get("S3_USE_SIGV4") and
                not config.get(asc.bucket_name)):
            calling_format = bsc.SubdomainCallingFormat()

        conn = boto.connect_s3(
            host=config[asc.host_name],
            aws_access_key_id=config[tac.key_id],
            aws_secret_access_key=config[tac.secret_key],
            security_token=config.get('aws_session_token'),
            proxy=config.get(tac.proxy_hostname),
            proxy_port=config.get(tac.proxy_port),
            proxy_user=config.get(tac.proxy_username),
            proxy_pass=config.get(tac.proxy_password),
            is_secure=True,
            validate_certs=True,
            calling_format=calling_format)
    if isinstance(conn.host, unicode):
        conn.host = conn.host.encode('utf-8')
    return conn


def _key_id_not_in_records(e):
    no_keyid = ("The AWS Access Key Id you provided does not exist "
                "in our records")
    return e.status == 403 and no_keyid in e.body


def validate_region_and_bucket(region, config):
    conn = _create_s3_connection(config, region)
    try:
        conn.get_bucket(config[asc.bucket_name])
    except Exception:
        return False
    return True


def get_region_for_bucketname(config):
    """
    :config: dict
    {
        key_id: xxx (required),
        secret_key: xxx (required),
        host: xxx,
        bucket_name: xxx,
        proxy_hostname: xxx,
        proxy_port: xxx,
        proxy_username: xxx,
        proxy_password: xxx,
    }
    """

    if not config.get(asc.bucket_name):
        if config.get(tac.region):
            return config[tac.region]
        return ""

    if config.get(tac.region):
        res = validate_region_and_bucket(config[tac.region], config)
        if res:
            return config[tac.region]

    conn = _create_s3_connection(config, "us-east-1")
    try:
        conn.get_bucket(config[asc.bucket_name])
    except boto2_s3_patch.RegionRedirection as e:
        return e.region_name
    except Exception:
        logger.exception("Failed to detect S3 bucket region.",
                         bucket_name=config[asc.bucket_name])
        raise

    return "us-east-1"


def create_s3_connection(config):
    """
    :config: dict
    {
        key_id: xxx (required),
        secret_key: xxx (required),
        host_name: xxx,
        bucket_name: xxx,
        region: xxx,
        proxy_hostname: xxx,
        proxy_port: xxx,
        proxy_username: xxx,
        proxy_password: xxx,
    }
    """

    if not config.get(asc.host_name):
        config[asc.host_name] = asc.default_host

    if config[asc.host_name] == asc.default_host:
        config[tac.region] = get_region_for_bucketname(config)
    else:
        pattern = r"s3[.-]([\w-]+)\.amazonaws.com"
        m = re.search(pattern, config[asc.host_name])
        if m:
            config[tac.region] = m.group(1)
        else:
            config[tac.region] = "us-east-1"
    return _create_s3_connection(config, config[tac.region])


def _build_regex(regex_str):
    if regex_str:
        exact_str = regex_str if regex_str[-1] == "$" else regex_str + "$"
        return re.compile(exact_str)
    else:
        return None


def _match_regex(white_matcher, black_matcher, key):
    if white_matcher is not None:
        if white_matcher.search(key.name):
            return True
    else:
        if black_matcher is None or not black_matcher.search(key.name):
            return True
    return False


def format_utc_datetime(dt):
    if not dt:
        return dt

    dt = dt.strip()
    fmt = "%Y-%m-%dT%H:%M:%S.000Z"
    if not dt.endswith(".000Z"):
        fmt = "%Y-%m-%dT%H:%M:%S"
    return datetime.strptime(dt, fmt)


@retry(retries=3)
def get_all_keys(bucket, prefix='', delimiter='', marker='', headers=None,
                 encoding_type=None):
    return bucket.get_all_keys(prefix=prefix, marker=marker,
                               delimiter=delimiter, headers=headers,
                               encoding_type=encoding_type)


def bucket_lister(bucket, prefix='', delimiter='', marker='', headers=None,
                  encoding_type=None):
    more_results = True
    k = None
    while more_results:
        rs = get_all_keys(bucket, prefix=prefix, marker=marker,
                          delimiter=delimiter, headers=headers,
                          encoding_type=encoding_type)
        for k in rs:
            yield k
        if k:
            marker = rs.next_marker or k.name
        if marker and encoding_type == "url":
            marker = unquote_str(marker)
        more_results = rs.is_truncated


def get_keys(bucket, prefix="", whitelist=None, blacklist=None,
             last_modified="", excluded=None,
             storage_classes=("STANDARD", "STANDARD_IA", "REDUCED_REDUNDANCY")):
    """
    return keys which meet:
    1. whitelist and not blacklist
    2. storage_class and not folder
    3. key.last_modified >= last_modified and not in excluded or in excluded
       but last modified time have been changed
    :params: exlcuded is a dict of dict each sub dict object must contains
    {
    "last_modified": xxx
    }
    """

    black_matcher = _build_regex(blacklist)
    white_matcher = _build_regex(whitelist)
    if last_modified is None:
        last_modified = ""

    keys = bucket_lister(bucket, prefix=prefix)
    for key in keys:
        if storage_classes and key.storage_class not in storage_classes:
            logger.info("Skipped this key because storage class does not match"
                        "(only supports STANDARD, STANDARD_IA and REDUCED_REDUNDANCY).",
                        key_name=key.name, storage_class=key.storage_class)
            continue

        if key.name.endswith("/"):
            continue

        if key.last_modified >= last_modified:
            if excluded and key.name in excluded:
                # Last modified time is not changed
                if excluded[key.name][asc.last_modified] >= key.last_modified:
                    continue

            if _match_regex(white_matcher, black_matcher, key):
                yield key


def detect_unicode_by_bom(data):
    if data[:2] == "\xFE\xFF":
        return "UTF-16BE"
    if data[:2] == "\xFF\xFE":
        return "UTF-16LE"
    if data[:4] == "\x00\x00\xFE\xFF":
        return "UTF-32BE"
    if data[:4] == "\xFF\xFE\x00\x00":
        return "UTF-32LE"
    return "UTF-8"


def get_decoder(encoding, data):
    if not encoding:
        if data:
            encoding = detect_unicode_by_bom(data)
        else:
            encoding = "UTF-8"

    try:
        decoder = codecs.getincrementaldecoder(encoding)(errors="replace")
        return decoder, encoding
    except LookupError:
        decoder = codecs.getincrementaldecoder("UTF-8")(errors="replace")
        return decoder, encoding


def normalize_to_iso8601(time_string):
    date_time = parse_timestamp(time_string)
    return date_time.strftime('%Y-%m-%dT%H:%M:%S.000Z')
