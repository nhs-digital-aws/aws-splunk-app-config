from datetime import datetime, timedelta
import boto3
import boto3.session
import botocore.client
from botocore.utils import InstanceMetadataFetcher
from dateutil.tz import tzutc
from dateutil.parser import parse as parse_datetime
from splunksdc import log as logging
from splunksdc.config import StanzaParser, BooleanField, StringField, IntegerField

logger = logging.get_module_logger()


class AWSCredentialsError(Exception):
    pass


class AWSRawCredentials(object):
    def __init__(self, aws_access_key_id, aws_secret_access_key,
                 aws_session_token=None, expiration=None):
        """

        :param aws_access_key_id:
        :param aws_secret_access_key:
        :param aws_session_token:
        :param expiration: A datetime object
        """
        self._aws_access_key_id = aws_access_key_id
        self._aws_secret_access_key = aws_secret_access_key
        self._aws_session_token = aws_session_token
        self._expiration = expiration

    def client(self, service_name, region_name, boto_session=None):
        if not boto_session:
            boto_session = boto3
        params = {
            'region_name': region_name,
            'aws_access_key_id': self._aws_access_key_id,
            'aws_secret_access_key': self._aws_secret_access_key,
            'aws_session_token': self._aws_session_token,
        }
        if service_name == 's3v4':
            params['config'] = botocore.client.Config(signature_version='s3v4')
            service_name = 's3'

        return boto_session.client(service_name, **params)

    @property
    def aws_access_key_id(self):
        return self._aws_access_key_id

    @property
    def aws_secret_access_key(self):
        return self._aws_secret_access_key

    @property
    def aws_session_token(self):
        return self._aws_session_token

    @property
    def expiration(self):
        return self._expiration


class EC2InstanceRoleProvider(object):
    """
    Query Role Credentials by EC2 instance metadata service
    """

    def __call__(self):
        logger.info('Fetch ec2 instance credentials.')
        fetcher = InstanceMetadataFetcher(
            timeout=5.0,
            num_attempts=10
        )
        response = fetcher.retrieve_iam_role_credentials()
        if not response:
            # There's no way to know exactly reason,
            # because botocore doesn't pass back the response.
            # What only we can do here is raise a general error.
            raise AWSCredentialsError('Retrieve ec2 instance credentials failed.')
        key_id = response['access_key']
        secret_key = response['secret_key']
        token = response['token']
        expiration = response['expiry_time']
        if not isinstance(expiration, datetime):
            expiration = parse_datetime(expiration)

        return AWSRawCredentials(key_id, secret_key, token, expiration)


class StaticAccessKeyProvider(object):
    def __init__(self, key_id, secret_key):
        self._key_id = key_id
        self._secret_key = secret_key

    def __call__(self):
        return AWSRawCredentials(self._key_id, self._secret_key)


class AWSAccount(object):
    DEFAULT_REGION = {
        1: 'us-east-1',
        2: 'us-gov-west-1',
        4: 'cn-north-1',
    }

    def __init__(self, profile):
        self._profile = profile

    def get_default_region(self):
        return self.DEFAULT_REGION.get(self._profile.category)

    def _create_credentials_provider(self):
        profile = self._profile
        if profile.iam:
            return EC2InstanceRoleProvider()
        return StaticAccessKeyProvider(profile.key_id, profile.secret_key)

    def load_raw_credentials(self):
        provider = self._create_credentials_provider()
        credentials = provider()
        return credentials

    def load_credentials(self, boto_session=None):
        credentials = self.load_raw_credentials()
        region_name = self.get_default_region()
        sts = credentials.client('sts', region_name, boto_session)
        identity = sts.get_caller_identity()
        arn = identity.get('Arn')

        return AWSCredentials(
            aws_access_key_id=credentials.aws_access_key_id,
            aws_secret_access_key=credentials.aws_secret_access_key,
            aws_session_token=credentials.aws_session_token,
            expiration=credentials.expiration,
            arn=arn,
        )


class AWSIAMRole(object):
    def __init__(self, profile):
        self._arn = profile.arn

    def load_credentials(self, account, duration, boto_session=None):
        arn = self._arn
        source = account.load_raw_credentials()
        region_name = account.get_default_region()
        sts = source.client('sts', region_name, boto_session)
        logger.info('request role credentials', arn=arn, duration=duration)

        response = sts.assume_role(
            RoleArn=arn,
            RoleSessionName='splunk_ta_aws',
            DurationSeconds=duration
        )
        content = response['Credentials']

        return AWSCredentials(
            aws_access_key_id=content['AccessKeyId'],
            aws_secret_access_key=content['SecretAccessKey'],
            aws_session_token=content['SessionToken'],
            expiration=content['Expiration'],
            arn=arn
        )


class AWSCredentials(AWSRawCredentials):
    _MIN_TTL = timedelta(minutes=5)

    def __init__(self, aws_access_key_id, aws_secret_access_key,
                 aws_session_token, expiration, arn):
        super(AWSCredentials, self).__init__(
            aws_access_key_id, aws_secret_access_key,
            aws_session_token, expiration
        )
        self._arn = arn
        self._account_id = arn.split(':')[4]

    @property
    def arn(self):
        return self._arn

    @property
    def account_id(self):
        return self._account_id

    def need_retire(self, threshold=_MIN_TTL):
        if not self.expiration:
            return False
        now = datetime.utcnow().replace(tzinfo=tzutc())
        delta = self.expiration - now
        return delta < threshold


class AWSCredentialsProviderFactory(object):

    def __init__(self, config):
        self._config = config

    def create(self, aws_account_name, aws_iam_role_name):
        settings = self._load_assume_role_settings()
        aws_account = self._load_aws_account(aws_account_name)
        if aws_iam_role_name:
            aws_iam_role = self._load_aws_iam_role(aws_iam_role_name)
            return AWSAssumedRoleProvider(settings, aws_account, aws_iam_role)

        return AWSAccountProvider(aws_account)

    def _load_aws_account(self, aws_account_name):
        if not aws_account_name:
            raise AWSCredentialsError('The name of account is invalid.')

        name = 'splunk_ta_aws/settings/account'
        content = self._config.load(name, stanza=aws_account_name, virtual=True)
        parser = StanzaParser([
            BooleanField('iam', default=False),
            StringField('key_id'),
            StringField('secret_key'),
            IntegerField('category', default=0)
        ])
        profile = parser.parse(content)
        return AWSAccount(profile)

    def _load_aws_iam_role(self, aws_iam_role_name):
        if not aws_iam_role_name:
            raise AWSCredentialsError('The name of IAM role is invalid.')

        name = 'splunk_ta_aws/settings/splunk_ta_aws_iam_role'
        content = self._config.load(name, stanza=aws_iam_role_name, virtual=True)
        parser = StanzaParser([StringField('arn')])
        profile = parser.parse(content)
        return AWSIAMRole(profile)

    def _load_assume_role_settings(self):
        stanza = self._config.load('aws_settings', stanza='assume_role')
        parser = StanzaParser([
            IntegerField('duration', default=3600, lower=900, upper=3600)
        ])
        return parser.parse(stanza)


class AWSCredentialsProvider(object):
    def load(self):
        pass


class AWSAccountProvider(AWSCredentialsProvider):
    def __init__(self, aws_account):
        self._aws_account = aws_account

    def load(self):
        """
        Get credentials of an account
        :return: An instance of AWSCredentials
        """
        return self._aws_account.load_credentials()


class AWSAssumedRoleProvider(AWSCredentialsProvider):
    def __init__(self, settings, aws_account, aws_iam_role):
        self._settings = settings
        self._aws_account = aws_account
        self._aws_iam_role = aws_iam_role

    def load(self):
        """
        Get credentials of an IAM role
        :return: An instance of AWSCredentials
        """

        logger.info('Begin loading assumed role credentials.')
        aws_account = self._aws_account
        aws_iam_role = self._aws_iam_role
        assume_role_duration = self._settings.duration
        credentials = aws_iam_role.load_credentials(aws_account, assume_role_duration)
        return credentials


class AWSCredentialsCache(object):
    def __init__(self, provider):
        self._provider = provider
        self._credentials = provider.load()

    def refresh(self):
        self._credentials = self._provider.load()

    def need_retire(self, ttl):
        return self._credentials.need_retire(ttl)

    def client(self, service_name, region_name, boto_session=None):
        return self._credentials.client(service_name, region_name, boto_session)



