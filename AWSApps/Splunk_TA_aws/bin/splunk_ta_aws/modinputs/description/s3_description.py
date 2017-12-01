import boto3
import splunksdc.log as logging
import description as desc
import splunk_ta_aws.common.ta_aws_consts as tac
from botocore.client import Config
from botocore.exceptions import ClientError

logger = logging.get_module_logger()

skipped_error_code_list = ['NoSuchLifecycleConfiguration',
                           'NoSuchCORSConfiguration', 'NoSuchTagSet',
                           'UnsupportedArgument']


@desc.refresh_credentials
def s3_buckets(config):
    s3_client = desc.BotoRetryWrapper(boto_client=boto3.client(
        's3',
        region_name=config.get(tac.region),
        aws_access_key_id=config[tac.key_id],
        aws_secret_access_key=config[tac.secret_key],
        aws_session_token=config.get('aws_session_token'),
        config=Config(signature_version='s3v4')
    ))

    bucket_arr = s3_client.list_buckets()['Buckets']

    if bucket_arr is not None and len(bucket_arr) > 0:
        for bucket in bucket_arr:
            # add account id
            # TODO assume role changes this
            bucket[tac.account_id] = config[tac.account_id]

            # add other info
            for operation in ['get_bucket_accelerate_configuration',
                              'get_bucket_cors', 'get_bucket_lifecycle',
                              'get_bucket_location', 'get_bucket_logging',
                              'get_bucket_tagging']:
                try:
                    response = getattr(s3_client, operation)(Bucket = bucket['Name'])
                    response.pop('ResponseMetadata', None)

                    # http://docs.aws.amazon.com/AmazonS3/latest/API/RESTBucketGETlocation.html#RESTBucketGETlocation-responses-response-elements
                    # if location is us-east-1, it will return None
                    if operation == 'get_bucket_location' and response['LocationConstraint'] is None:
                        response['LocationConstraint'] = 'us-east-1'

                    bucket.update(response)

                except ClientError as client_error:
                    if 'Code' not in client_error.response['Error'] or client_error.response['Error']['Code'] not in skipped_error_code_list:
                        logger.exception('%s operation is invalid in %s bucket.' % (operation, bucket['Name']))
                    continue

                except Exception:
                    logger.exception('An error occurred when attempting %s operation on %s bucket.' % (operation, bucket['Name']))
                    continue

            bucket[tac.region] = bucket['LocationConstraint']

            yield desc.serialize(bucket)
