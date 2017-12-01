from __future__ import absolute_import
import time
import os
import shutil
from splunksdc import logging, environ
from splunksdc.collector import SimpleCollectorV1
from splunksdc.config import StanzaParser, IntegerField, StringField
from splunksdc.config import LogLevelField, DateTimeField
from splunksdc.utils import LogExceptions, LogWith
from splunk_ta_aws import set_log_level
from splunk_ta_aws.common.credentials import AWSCredentialsProviderFactory
from splunk_ta_aws.common.credentials import AWSCredentialsCache
from splunk_ta_aws.common.proxy import ProxySettings
from splunk_ta_aws.common.s3 import S3Bucket
from .handler import AWSLogsHandler
from .cloudtrail_logs import CloudTrailLogsDelegate
from .elb_access_logs import ELBAccessLogsDelegate
from .s3_access_logs import S3AccessLogsDelegate
from .cloudfront_access_logs import CloudFrontAccessLogsDelegate


logger = logging.get_module_logger()


class UnsupportedLogType(Exception):
    pass


class AWSLogsSettings(object):
    @classmethod
    def load(cls, config):
        content = config.load('aws_settings', stanza='splunk_ta_aws_logs')
        parser = StanzaParser([
            LogLevelField('log_level', default='WARNING')
        ])
        settings = parser.parse(content)
        return cls(settings)

    def __init__(self, settings):
        self._settings = settings

    def setup_log_level(self):
        set_log_level(self._settings.log_level)


class AWSLogsProfile(object):
    def __init__(self, log_type, delegate):
        self._type = log_type
        self._sourcetype = 'aws:' + log_type
        self._delegate = delegate

    @property
    def type(self):
        return self._type

    @property
    def sourcetype(self):
        return self._sourcetype

    def create_delegate(self, args):
        return self._delegate.build(args)


class AWSLogsDataInput(object):
    def __init__(self, stanza, registry):
        self._stanza = stanza
        self._name = stanza.name
        self._start_time = int(time.time())
        self._lookup = {}
        for profile in registry:
            self._lookup[profile.type] = profile

    def create_log_profile(self):
        log_type = self._stanza.content.get('log_type', '')
        log_type = log_type.lower()
        profile = self._lookup.get(log_type)
        if not profile:
            raise UnsupportedLogType(log_type)
        return profile

    def parse_options(self):
        parser = StanzaParser([
            IntegerField('max_retries', default=-1, lower=-1, upper=1000),
            IntegerField('max_fails', default=10000, lower=0, upper=10000),
            IntegerField('max_number_of_process', default=2, lower=1, upper=64),
            IntegerField('max_number_of_thread', default=4, lower=1, upper=64)
        ])
        return self._extract(parser)

    def parse_extra(self):
        parser = StanzaParser([
            StringField('log_file_prefix', default=''),
            DateTimeField('log_start_date', default='1970-1-1'),
            StringField('log_name_format', default=''),
            StringField('log_partitions', default=''),
        ])
        return self._extract(parser)

    def create_event_metadata(self, profile):
        stanza_name = self._assemble_stanza_id()
        parser = StanzaParser([
            StringField('index'),
            StringField('host'),
            StringField('sourcetype', fillempty=profile.sourcetype),
            StringField('stanza', fillempty=stanza_name)
        ])
        return self._extract(parser)

    def create_credentials(self, config):
        parser = StanzaParser([
            StringField('aws_account', required=True),
            StringField('aws_iam_role'),
        ])
        args = self._extract(parser)
        factory = AWSCredentialsProviderFactory(config)
        provider = factory.create(args.aws_account, args.aws_iam_role)
        return AWSCredentialsCache(provider)

    def create_bucket(self):
        parser = StanzaParser([
            StringField('bucket_name', required=True),
            StringField('bucket_region', required=True),
        ])
        args = self._extract(parser)
        return S3Bucket(args.bucket_name, args.bucket_region)

    def _extract(self, parser):
        return parser.parse(self._stanza.content)

    def _assemble_stanza_id(self):
        stanza = self._stanza
        return stanza.kind + '://' + stanza.name

    @property
    def name(self):
        return self._name

    @property
    def start_time(self):
        return self._start_time

    @LogWith(datainput=name, start_time=start_time)
    @LogExceptions(logger, 'Data input was interrupted by an unhandled exception.', lambda e: -1)
    def run(self, app, config):
        settings = AWSLogsSettings.load(config)
        settings.setup_log_level()
        proxy = ProxySettings.load(config)
        proxy.hook_boto3_get_proxies()

        data_input_name = self._name
        profile = self.create_log_profile()
        extras = self.parse_extra()
        delegate = profile.create_delegate(extras)
        metadata = self.create_event_metadata(profile)
        options = self.parse_options()
        credentials = self.create_credentials(config)
        bucket = self.create_bucket()

        handler = AWSLogsHandler(
            settings, proxy, data_input_name, metadata, options,
            bucket, delegate, credentials
        )
        return handler.run(app, config)


def modular_input_main(app, config):
    inputs = app.inputs()
    datainput = AWSLogsDataInput(inputs[0], [
        AWSLogsProfile('cloudtrail', CloudTrailLogsDelegate),
        AWSLogsProfile('elb:accesslogs', ELBAccessLogsDelegate),
        AWSLogsProfile('cloudfront:accesslogs', CloudFrontAccessLogsDelegate),
        AWSLogsProfile('s3:accesslogs', S3AccessLogsDelegate)
    ])
    return datainput.run(app, config)


def main():
    arguments = {
        'aws_account': {
            'title': 'The AWS account name.'
        },
        'aws_iam_role': {
            'title': 'Assume Role.',
            'required_on_create': False
        },
        'log_type': {
            'title': 'What is kind of log.'
        },
        'bucket_name': {
            'title': 'Where are the logs located.'
        },
        'bucket_region': {
            'title': 'Where is the bucket located.'
        },
        'host_name': {
            'title': 'Host the bucket located. Used to detect bucket_region.'
        },
        'log_file_prefix': {
            'title': 'Please read document for details.'
        },
        'log_start_date': {
            'title': 'The logs earlier than this date would not be ingested.'
        },
        'log_name_format': {
            'title': 'Please Read document for details.'
        },
        'max_retries': {
            'title': 'Max Retries',
            'required_on_create': False
        },
        'max_fails': {
            'title': 'Max Fails',
            'required_on_create': False
        },
        'max_number_of_process': {
            'title': 'How many worker processes could be running in parallel for each input',
            'required_on_create': False
        },
        'max_number_of_thread': {
            'title': 'How many worker threads could be running in parallel for each process',
            'required_on_create': False
        }
    }

    SimpleCollectorV1.main(
        modular_input_main,
        title='AWS S3 Incremental Logs',
        use_single_instance=False,
        arguments=arguments,
        log_file_sharding=True,
    )


def create_data_input(name, *args, **kwargs):
    remove_checkpoints(name)


def delete_data_input(name, *args, **kwargs):
    remove_checkpoints(name)


def remove_checkpoints(name):
    root = environ.get_checkpoint_folder('splunk_ta_aws_logs')
    path = os.path.join(root, name)

    # try remove files for cloudtrail and elb
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)

    # try remove files for s3 and cloudfront
    path += '.ckpt'
    if os.path.isfile(path):
        os.remove(path)
