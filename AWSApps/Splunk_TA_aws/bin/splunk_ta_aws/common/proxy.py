import urllib2
import botocore.endpoint
from splunksdc import logging
from splunksdc.config import StanzaParser, StringField, BooleanField


logger = logging.get_module_logger()


class ProxySettings(object):
    @staticmethod
    def _wipe(settings):
        params = vars(settings).copy()
        del params['password']
        return params

    @classmethod
    def load(cls, config):
        content = config.load('splunk_ta_aws/splunk_ta_aws_settings_proxy', stanza='aws_proxy', virtual=True)
        parser = StanzaParser([
            BooleanField('proxy_enabled', rename='enabled'),
            StringField('host'),
            StringField('port'),
            StringField('username'),
            StringField('password')
        ])
        settings = parser.parse(content)
        logger.debug('Load proxy settings success.', **cls._wipe(settings))
        return cls(settings)

    def __init__(self, settings):
        self._settings = settings

    def _make_url(self, scheme):
        settings = self._settings
        endpoint = '{host}:{port}'.format(
            host=settings.host,
            port=settings.port
        )
        auth = None
        if settings.username and len(settings.username) > 0:
            auth = urllib2.quote(settings.username.encode(), safe='')
            if settings.password and len(settings.password) > 0:
                auth += ':'
                auth += urllib2.quote(settings.password.encode(), safe='')

        if auth:
            endpoint = auth + '@' + endpoint

        url = scheme + '://' + endpoint
        return url

    def hook_boto3_get_proxies(self):
        settings = self._settings
        http_url = self._make_url('http')
        https_url = self._make_url('https')

        def _get_proxies(creator, url):
            return {"http": http_url, "https": https_url}

        if settings.enabled:
            creator = botocore.endpoint.EndpointCreator
            creator._get_proxies = _get_proxies
            logger.info('Proxy is enabled.')
