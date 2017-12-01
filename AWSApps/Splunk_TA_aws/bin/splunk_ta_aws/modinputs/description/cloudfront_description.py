from boto.cloudfront import CloudFrontConnection

import splunksdc.log as logging
import splunk_ta_aws.common.ta_aws_consts as tac
import description as desc


logger = logging.get_module_logger()


class AWSCloudFrontConnection(CloudFrontConnection):

    def __init__(self,
                 aws_access_key_id=None,
                 aws_secret_access_key=None,
                 port=None,
                 proxy=None,
                 proxy_port=None,
                 host=CloudFrontConnection.DefaultHost,
                 debug=0,
                 security_token=None,
                 validate_certs=True,
                 profile_name=None,
                 https_connection_factory=None,
                 proxy_user=None,
                 proxy_pass=None
                 ):
        super(CloudFrontConnection, self).__init__(
            host,
            aws_access_key_id,
            aws_secret_access_key,
            True,
            port,
            proxy,
            proxy_port,
            debug=debug,
            security_token=security_token,
            validate_certs=validate_certs,
            https_connection_factory=https_connection_factory,
            profile_name=profile_name,
            proxy_user=proxy_user,
            proxy_pass=proxy_pass,
        )


def connect_cloudfront(config):
    conn = AWSCloudFrontConnection(
        aws_access_key_id=config.get(tac.key_id),
        aws_secret_access_key=config.get(tac.secret_key),
        security_token=config.get('aws_session_token'),
        proxy=config.get(tac.proxy_hostname),
        proxy_port=config.get(tac.proxy_port),
        proxy_user=config.get(tac.proxy_username),
        proxy_pass=config.get(tac.proxy_password),
    )
    return desc.BotoRetryWrapper(boto_client=conn)


# TODO: boto3 supports pagination
@desc.describe_pagination
@desc.refresh_credentials
def cloudfront_distributions(config):
    keys = ["cnames", "comment", "domain_name", "enabled", "etag",  "id",
            "last_modified_time", "origin", "status", "streaming",
            "trusted_signers"]
    origin_keys = ["dns_name"]
    conn = connect_cloudfront(config)
    distributes = conn.get_all_distributions()
    results = desc.pop_description_results(
        distributes, keys, {tac.account_id: config[tac.account_id]},
        pop_region_name=False, raw_event=True)
    for i, result in enumerate(results):
        result["origin"] = desc.pop_description_result(
            result["origin"], origin_keys, {},
            pop_region_name=False, raw_event=True)
        results[i] = desc.serialize(result)
    return results, {}
