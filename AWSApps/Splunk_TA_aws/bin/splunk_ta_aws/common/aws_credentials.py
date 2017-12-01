import json
import boto3
from datetime import datetime, timedelta
from dateutil.tz import tzutc
from dateutil.parser import parse as parse_datetime
from botocore.utils import InstanceMetadataFetcher
from splunksdc import logging


logger = logging.get_module_logger()


class AWSCredentialsError(Exception):
    pass


class AWSAccountError(AWSCredentialsError):
    def __init__(self, message, aws_account):
        super(AWSAccountError, self).__init__(message)
        self.aws_account = aws_account


class AWSIAMRoleError(AWSCredentialsError):
    def __init__(self, message, aws_iam_role):
        super(AWSIAMRoleError, self).__init__(message)
        self.aws_iam_role = aws_iam_role


class StanzaReader(object):
    def __init__(self, stanza):
        self._stanza = stanza

    def get_boolean(self, key, default):
        value = self._stanza.get(key)
        if value:
            return int(value) != 0
        return default

    def get_integer(self, key, default):
        value = self._stanza.get(key)
        if value:
            return int(value)
        return default

    def get(self, key, default=None):
        return self._stanza.get(key, default)


class AWSAccount(object):
    def __init__(self):
        self.is_ec2_instance_role = None
        self.access_key_id = None
        self.secret_access_key = None
        self.category = None


class AWSAccountService(object):
    @classmethod
    def load(cls, config):
        content = config.load('splunk_ta_aws/settings/account', virtual=True)
        accounts = cls()
        for name, stanza in content.items():
            accounts.add(name, stanza)
        return accounts

    def __init__(self):
        self._table = dict()

    def __contains__(self, name):
        return name in self._table

    def __getitem__(self, name):
        return self._table[name]

    def add(self, name, stanza):
        reader = StanzaReader(stanza)
        account = AWSAccount()
        account.is_ec2_instance_role = reader.get_boolean('iam', False)
        account.access_key_id = reader.get('key_id')
        account.secret_access_key = reader.get('secret_key')
        account.category = reader.get_integer('category', 0)
        self._table[name] = account


class AWSIAMRole(object):
    def __init__(self):
        self.arn = None


class AWSIAMRoleService(object):
    @classmethod
    def load(cls, config):
        content = config.load('splunk_ta_aws/settings/splunk_ta_aws_iam_role', virtual=True)
        roles = cls()
        for name, stanza in content.items():
            roles.add(name, stanza)
        return roles

    def __init__(self):
        self._table = dict()

    def __contains__(self, name):
        return name in self._table

    def __getitem__(self, name):
        return self._table[name]

    def add(self, name, stanza):
        reader = StanzaReader(stanza)
        role = AWSIAMRole()
        role.arn = reader.get('arn')
        self._table[name] = role


class AWSCredentials(object):
    _MIN_TTL = timedelta(minutes=5)

    def __init__(self):
        self.aws_access_key_id = None
        self.aws_secret_access_key = None
        self.aws_session_token = None
        self.expiration = None
        self.category = None
        self.arn = None

    def need_retire(self, threshold=_MIN_TTL):
        if not self.expiration:
            return False
        now = datetime.utcnow().replace(tzinfo=tzutc())
        delta = self.expiration - now
        return delta < threshold

    @property
    def account_id(self):
        return self.arn.split(':')[4] if self.arn else None


class AWSCredentialsService(object):

    DEFAULT_REGIONS = {
        1: 'us-east-1',
        2: 'us-gov-west-1',
        4: 'cn-north-1',
    }

    def __init__(self, accounts, roles, **kwargs):
        self._accounts = accounts
        self._roles = roles
        self._duration = kwargs.pop('duration', 3600)

    def load(self, aws_account_name, aws_iam_role_name=None):
        logger.info(
            'begin loading credentials',
            aws_account=aws_account_name,
            aws_iam_role=aws_iam_role_name
        )
        credentials = self._load(aws_account_name, aws_iam_role_name)
        expiration = str(credentials.expiration)
        logger.info(
            'load credentials succeed',
            arn=credentials.arn,
            expiration=expiration
        )
        return credentials

    def _load(self, aws_account_name, aws_iam_role_name=None):
        if aws_account_name not in self._accounts:
            raise AWSAccountError('account not found', aws_account_name)
        account = self._accounts[aws_account_name]

        if account.category not in self.DEFAULT_REGIONS:
            raise AWSAccountError('account category invalid', aws_account_name)

        region_name = self.DEFAULT_REGIONS[account.category]

        if not aws_iam_role_name:
            aws_iam_role_name = ''
        if len(aws_iam_role_name):
            if aws_iam_role_name not in self._roles:
                raise AWSIAMRoleError('iam role not found', aws_iam_role_name)
            role = self._roles[aws_iam_role_name]
            return self._load_role_credentials(account, role, region_name)

        return self._load_source_credentials(account, region_name)

    @classmethod
    def _load_source_credentials(cls, account, region_name):
        key_id = account.access_key_id
        secret_key = account.secret_access_key
        token = None
        expiration = None

        if account.is_ec2_instance_role:
            logger.info('fetch ec2 instance credentials')
            fetcher = InstanceMetadataFetcher(
                timeout=5.0,
                num_attempts=10
            )
            response = fetcher.retrieve_iam_role_credentials()
            key_id = response['access_key']
            secret_key = response['secret_key']
            token = response['token']
            expiration = response['expiry_time']
            if not isinstance(expiration, datetime):
                expiration = parse_datetime(expiration)

        sts = cls.create_sts_client(key_id, secret_key, token, region_name)
        identity = sts.get_caller_identity()
        arn = identity.get('Arn')

        credentials = AWSCredentials()
        credentials.aws_access_key_id = key_id
        credentials.aws_secret_access_key = secret_key
        credentials.aws_session_token = token
        credentials.expiration = expiration
        credentials.category = account.category
        credentials.arn = arn
        return credentials

    def _load_role_credentials(self, account, role, region_name):
        source = self._load_source_credentials(account, region_name)
        sts = self.create_sts_client(
            source.aws_access_key_id,
            source.aws_secret_access_key,
            source.aws_session_token,
            region_name
        )

        logger.info('request role credentials', arn=role.arn, duration=self._duration)

        response = sts.assume_role(
            RoleArn=role.arn,
            RoleSessionName='splunk_ta_aws',
            DurationSeconds=self._duration
        )
        content = response['Credentials']
        credentials = AWSCredentials()
        credentials.aws_access_key_id = content['AccessKeyId']
        credentials.aws_secret_access_key = content['SecretAccessKey']
        credentials.aws_session_token = content['SessionToken']
        credentials.expiration = content['Expiration']
        credentials.category = account.category
        credentials.arn = role.arn
        return credentials

    @classmethod
    def create_sts_client(cls, key_id, secret_key, token, region_name):
        return boto3.client(
            'sts',
            aws_access_key_id=key_id,
            aws_secret_access_key=secret_key,
            aws_session_token=token,
            region_name=region_name,
        )

    @classmethod
    def load_accounts(cls, config):
        return AWSAccountService.load(config)

    @classmethod
    def load_roles(cls, config):
        return AWSIAMRoleService.load(config)

    @classmethod
    def create(cls, config):
        stanza = config.load('aws_settings', stanza='assume_role')
        reader = StanzaReader(stanza)
        duration = reader.get_integer('duration', 3600)
        duration = max(900, duration)
        duration = min(3600, duration)
        accounts = cls.load_accounts(config)
        roles = cls.load_roles(config)
        return AWSCredentialsService(accounts, roles, duration=duration)