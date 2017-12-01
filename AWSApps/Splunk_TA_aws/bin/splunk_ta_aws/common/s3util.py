import logging
import re

import boto.ec2
import boto.sqs
import boto.ec2.cloudwatch
import boto.s3.connection
import boto.s3.prefix
import boto.exception

from proxy_conf import ProxyManager

import splunk_ta_aws.common.ta_aws_consts as tac
import splunk_ta_aws.common.proxy_conf as pc
import splunk_ta_aws.modinputs.generic_s3.aws_s3_consts as asc
import splunk_ta_aws.modinputs.generic_s3.aws_s3_common as s3common

from splunksdc import log as logging

logger = logging.get_module_logger()


class GlobalSettingUndefinedException(Exception):
    pass


try:
    # TODO(ver 2.0.0): Make some changes if needed. See below comments.
    # This implementation is bad because getMgmtUri() is used
    # to get splunkd host. While this is in line with exsiting
    # ProxyManager and CredentialManager and thus in line with
    # all modular inputs in 1.1.x, so it is still used in 1.2.0.
    from splunktalib.conf_manager.conf_manager import ConfManager
    import splunktalib.common.util as utils
    import splunk.clilib.cli_common as scc

    def get_global_is_secure(session_key):
        conf_manager = ConfManager(scc.getMgmtUri(), session_key)
        conn = conf_manager.get_stanza('aws_global_settings',
                                       'aws_connection',
                                       do_reload=False)
        return (utils.is_true(conn["is_secure"]),
                utils.is_true(conn["verify_certificates"]))
except:
    def get_global_is_secure(session_key):
        raise GlobalSettingUndefinedException(
            'Global setting aws_connection.is_secure is not defined')


def connect_s3_with_bucket(key_id, secret_key, session_key, bucket_name,
                           host="s3.amazonaws.com", is_secure=True,
                           validate_certs=True):
    calling_format = boto.s3.connection.SubdomainCallingFormat()
    if bucket_name and "." in bucket_name:
        calling_format = boto.s3.connection.OrdinaryCallingFormat()
    return connect_s3(key_id, secret_key, session_key, host, is_secure,
                      validate_certs, calling_format)


def connect_s3(key_id, secret_key, session_key, host="s3.amazonaws.com",
               is_secure=True, validate_certs=True,
               calling_format=boto.s3.connection.SubdomainCallingFormat(),
               security_token=None):
    logger.debug("Connect to s3")
    pm = ProxyManager(session_key)
    proxy = pm.get_proxy()
    if proxy is None or not proxy.get_enable():
        s3_conn = boto.s3.connection.S3Connection(aws_access_key_id=key_id,
                                                  aws_secret_access_key=secret_key,
                                                  host=host,
                                                  is_secure=is_secure,
                                                  validate_certs=validate_certs,
                                                  security_token=security_token,
                                                  calling_format=calling_format)
        return s3_conn
    else:
        logger.debug("Connect to s3 with proxy!")
        is_secure = True
        validate_certs = True
        proxy_info = proxy.get_proxy_info()

        proxy_host = proxy_info['host']
        proxy_port = proxy_info['port']
        proxy_username = proxy_info['user']
        proxy_password = proxy_info['pass']

        if proxy_host is None:
            logger.error("Proxy host must be set!")
            return None

        try:
            s3_conn = boto.s3.connection.S3Connection(aws_access_key_id=key_id,
                                                      aws_secret_access_key=secret_key,
                                                      proxy=proxy_host,
                                                      proxy_port=proxy_port,
                                                      proxy_user=proxy_username,
                                                      proxy_pass=proxy_password,
                                                      host=host,
                                                      security_token=security_token,
                                                      is_secure=is_secure,
                                                      validate_certs=validate_certs,
                                                      calling_format=calling_format)
        except Exception as e:
            logger.log(logging.ERROR, "{}: {}", type(e).__name__, e)
            raise e

        logger.debug("Connect to s3 success")
        return s3_conn


def connect_s3_to_region(key_id, secret_key, session_key, region,
                         is_secure=True):
    logger.debug("Connect to s3")
    pm = ProxyManager(session_key)
    proxy = pm.get_proxy()
    try:
        is_secure, _ = get_global_is_secure(session_key)
    except:
        pass
    if proxy is None or not proxy.get_enable():
        s3_conn = boto.s3.connect_to_region(region,
                                            aws_access_key_id=key_id,
                                            aws_secret_access_key=secret_key,
                                            is_secure=is_secure)
        return s3_conn
    else:
        logger.debug("Connect to s3 with proxy!")
        proxy_info = proxy.get_proxy_info()

        proxy_host = proxy_info['host']
        proxy_port = proxy_info['port']
        proxy_username = proxy_info['user']
        proxy_password = proxy_info['pass']

        if proxy_host is None:
            logger.error("Proxy host must be set!")
            return None

        try:
            s3_conn = boto.s3.connect_to_region(region,
                                                aws_access_key_id=key_id,
                                                aws_secret_access_key=secret_key,
                                                proxy=proxy_host,
                                                proxy_port=proxy_port,
                                                proxy_user=proxy_username,
                                                proxy_pass=proxy_password,
                                                is_secure=is_secure)
        except Exception as e:
            logger.log(logging.ERROR, "{}: {}", type(e).__name__, e)
            raise e

        logger.debug("Connect to s3 success")
        return s3_conn


def connect_sqs(region, key_id, secret_key, session_key, is_secure=True):
    logger.debug("Connect to sqs")
    pm = ProxyManager(session_key)
    proxy = pm.get_proxy()
    try:
        is_secure, _ = get_global_is_secure(session_key)
    except:
        pass
    if proxy is None or not proxy.get_enable():
        sqs_conn = boto.sqs.connect_to_region(region,
                                              aws_access_key_id=key_id,
                                              aws_secret_access_key=secret_key,
                                              is_secure=is_secure)
        return sqs_conn
    else:
        logger.debug("Connect to sqs with proxy")
        proxy_info = proxy.get_proxy_info()

        host = proxy_info['host']
        port = proxy_info['port']
        username = proxy_info['user']
        password = proxy_info['pass']

        if host is None:
            logger.error("Proxy host must be set!")
            return None

        logger.debug("Connect to sqs with proxy start")
        try:
            sqs_conn = boto.sqs.connect_to_region(region,
                                                  aws_access_key_id=key_id,
                                                  aws_secret_access_key=secret_key,
                                                  proxy=host,
                                                  proxy_port=port,
                                                  proxy_user=username,
                                                  proxy_pass=password,
                                                  is_secure=is_secure)
        except Exception as e:
            logger.log(logging.ERROR, "{}: {}", type(e).__name__, e)
            raise e
        logger.debug("Connect to sqs success")
        return sqs_conn


def connect_cloudwatch(region, key_id, secret_key, session_key,
                       is_secure=True):
    logger.debug("Connect to cloudwatch ")
    pm = ProxyManager(session_key)
    proxy = pm.get_proxy()
    try:
        is_secure, _ = get_global_is_secure(session_key)
    except:
        pass
    if proxy is None or not proxy.get_enable():
        logger.debug("Connect to cloudwatch without proxy")
        try:
            conn = boto.ec2.cloudwatch.connect_to_region(region,
                                                         aws_access_key_id=key_id,
                                                         aws_secret_access_key=secret_key,
                                                         is_secure=is_secure)
        except Exception as e:
            logger.log(logging.ERROR, "{}: {}", type(e).__name__, e)
            raise e
        logger.debug("Connect to cloudwatch without proxy success")
        return conn
    else:
        logger.debug("Connect to cloudwatch with proxy")
        proxy_info = proxy.get_proxy_info()

        host = proxy_info['host']
        port = proxy_info['port']
        username = proxy_info['user']
        password = proxy_info['pass']

        if host is None:
            logger.error("Proxy host must be set!")
            return None

        logger.debug("Connect to cloudwatch with proxy start")
        try:
            conn = boto.ec2.cloudwatch.connect_to_region(region,
                                                         aws_access_key_id=key_id,
                                                         aws_secret_access_key=secret_key,
                                                         proxy=host,
                                                         proxy_port=port,
                                                         proxy_user=username,
                                                         proxy_pass=password,
                                                         is_secure=is_secure)
        except Exception as e:
            logger.log(logging.ERROR, "{}: {}", type(e).__name__, e)
            raise e
        logger.debug("Connect to cloudwatch success")
        return conn


def list_cloudwatch_namespaces(region, key_id, secret_key, session_key=None):
    return ["AWS/AutoScaling", "AWS/Billing", "AWS/CloudFront", "AWS/CloudSearch",
            "AWS/DynamoDB", "AWS/Events", "AWS/ECS", "AWS/ElastiCache",
            "AWS/EBS", "AWS/EC2", "AWS/EC2Spot", "AWS/ELB", "AWS/ApplicationELB", "AWS/ElasticMapReduce",
            "AWS/ES", "AWS/Kinesis", "AWS/Lambda", "AWS/Logs",
            "AWS/ML", "AWS/OpsWorks", "AWS/Redshift", "AWS/RDS", "AWS/Route53",
            "AWS/SNS", "AWS/SQS", "AWS/S3", "AWS/SWF", "AWS/StorageGateway",
            "AWS/WAF", "AWS/WorkSpaces"]


def exact_matcher(regex_str):
    if regex_str:
        exact_str = regex_str if regex_str[-1] == '$' else regex_str + '$'
        return re.compile(exact_str)
    else:
        return None


def blacklisted(key_name, black_matcher, white_matcher):
    # re.match() matches from the beginning
    # Add '$' to match end of word for strict match
    if white_matcher:
        if white_matcher.match(key_name):
            return False
    return True if (black_matcher and black_matcher.match(key_name)) else False


def get_keys(bucket, prefix="", delimiter="/", recursion_depth=0,
             object_keys=True, prefix_keys=True,
             whitelist=None, blacklist=None, last_modified_after=None,
             last_modified_before=None):
    """

    @param bucket:
    @param prefix:
    @param delimiter:
    @param recursion_depth:
    @param object_keys:
    @param prefix_keys:
    @param whitelist:
    @param blacklist:
    @param last_modified_after:
    @param last_modified_before:
    @return:
    """
    black_matcher = exact_matcher(blacklist)
    white_matcher = exact_matcher(whitelist)
    x = bucket.list(prefix=prefix, delimiter=delimiter)
    for key in x:

        if isinstance(key, boto.s3.prefix.Prefix):
            if prefix_keys and not blacklisted(key.name, black_matcher,
                                               white_matcher):
                yield key
            if recursion_depth or recursion_depth == -1:
                for child_key in get_keys(bucket, key.name, delimiter,
                                          max(-1, recursion_depth - 1),
                                          object_keys, prefix_keys, whitelist,
                                          blacklist,
                                          last_modified_after,
                                          last_modified_before):
                    yield child_key

        elif object_keys and key.name[-1] != delimiter and not blacklisted(
                key.name, black_matcher, white_matcher):
            do_yield = True
            if last_modified_after and key.last_modified < last_modified_after:
                do_yield = False
            if last_modified_before and key.last_modified >= last_modified_before:
                do_yield = False

            if do_yield:
                yield key


def get_queue(sqs_conn, queue_name):
    """
    Workaround boto bugs
    """

    queue = sqs_conn.get_queue(queue_name)
    if queue is not None:
        return queue

    if sqs_conn.region.name == "cn-north-1":
        queues = sqs_conn.get_all_queues(prefix=queue_name)
        for queue in queues:
            if queue.name == queue_name:
                return queue
        return None


def extract_region_from_key_name(key_name, region_rex):
    m = re.search(region_rex, key_name)
    if m:
        return m.group(1)
    return None


def create_s3_connection_from_keyname(key_id, secret_key, session_key,
                                      bucket_name, key_name, region_rex):
    region = extract_region_from_key_name(key_name, region_rex)
    if region and (region.startswith('us-gov-') or region.startswith('cn-')):
        return create_s3_connection(
            key_id, secret_key, session_key, bucket_name, region)
    return create_s3_connection(key_id, secret_key, session_key, bucket_name)


def create_s3_connection(key_id, secret_key, session_key, bucket_name=None,
                         region=None, host_name=asc.default_host,
                         aws_session_token=None):
    proxy_info = pc.get_proxy_info(session_key)
    proxy_info[tac.key_id] = key_id
    proxy_info[tac.secret_key] = secret_key
    proxy_info['aws_session_token'] = aws_session_token
    proxy_info[asc.host_name] = host_name
    proxy_info[asc.bucket_name] = bucket_name
    proxy_info[tac.region] = region
    return s3common.create_s3_connection(proxy_info)

