from __future__ import absolute_import

import json
import urllib

import solnlib.splunk_rest_client as src
import solnlib.utils as sutils
import splunklib.client as sc


import splunksdc.log as logging
logger = logging.get_context_logger('configuration_tool')


def get_session_key(splunk_info):
    if splunk_info.session_key:
        return splunk_info.session_key

    scheme, host, port = sutils.extract_http_scheme_host_port(
        splunk_info.mgmt_uri)
    service = sc.connect(scheme=scheme, host=host, port=port,
                         username=splunk_info.username,
                         password=splunk_info.password)
    return service.token


class AppConfigException(Exception):

    def __init__(self, message, failures):
        super(AppConfigException, self).__init__(message)
        self._failures = failures

    def failures(self):
        return self._failures


class AppConfigClient(object):

    def __init__(self, splunk_info, appname, owner='nobody'):
        '''
        :param splunk_info: `SplunkInfo` object
        :param appname: application/addon name
        :param owner: owner of the configuration, 'nobody' means globally
        shared
        '''

        self.appname = appname
        self.owner = owner
        self.splunk_info = splunk_info
        session_key = get_session_key(splunk_info)
        scheme, host, port = sutils.extract_http_scheme_host_port(
            splunk_info.mgmt_uri)
        self.rest_client = src.SplunkRestClient(
            session_key=session_key, app=appname, owner=owner,
            scheme=scheme, host=host, port=port)

    def create(self, endpoint, stanza):
        '''
        :param endpoint: rest endpoint of the resource
        :param stanza: properties of the stanza. dict object
        :return: None if successful, otherwise Exception will be raised
        '''

        self.rest_client.post(
            endpoint, owner=self.owner, app=self.appname, body=stanza,
            output_mode='json')

    def list(self, endpoint, stanza_name=None):
        '''
        :param endpoint: rest endpoint of the resource
        :return: a list of JSON objects if successful,
        otherwise Exception will be raised
        '''

        if stanza_name:
            endpoint = '{}/{}'.format(
                endpoint, urllib.quote(stanza_name, safe=''))

        response = self.rest_client.get(
            endpoint, owner=self.owner, app=self.appname,
            output_mode='json', count=-1)
        if response.status not in (200, 201):
            logger.error(
                "Failed to query", endpoint=endpoint,
                uri=self.splunk_info.mgmt_uri, reason=response.reason)
            raise Exception("Failed to query endpoint {}".format(response))
        return json.loads(response.body.read())['entry']

    def delete(self, endpoint, stanza_name):
        '''
        :param endpoint: rest endpoint of the resource
        :param stanza_name: name of the satanza to be deleted
        :return: None if successful otherwise Exception will be raised
        '''

        endpoint = '{}/{}'.format(
            endpoint, urllib.quote(stanza_name, safe=''))
        self.rest_client.delete(
            endpoint, owner=self.owner, app=self.appname, output_mode='json')


class AppConfigManager(object):

    def __init__(self, splunks, appname, owner='nobody'):
        self.appname = appname
        self.owner = owner
        self.splunks = splunks
        self.app_clients = {}

    def create(self, endpoint, hostname, stanzas):
        '''
        Create resource in a loop

        :param endpoint: resource rest API endpoint
        :param hostname: hostname of the box
        :param stanzas: array of dict containing stanza context to be created
        :return: None if all good, otherwise throw AppConfigException
        at the end
        '''

        failures = []
        client = self._get_client(hostname)
        for stanza in stanzas:
            try:
                client.create(endpoint, stanza)
            except Exception as e:
                failures.append([hostname, endpoint, stanza['name']])
                logger.error('Failure', stanza=stanza['name'], error=e.message)
            else:
                logger.info('Success', stanza=stanza['name'])

        if failures:
            raise AppConfigException('Failed to create', failures)

    def delete(self, endpoint, hostname, stanza_names):
        '''
        Delete resource in a loop

        :param endpoint: resource rest API endpoint
        :param hostname: hostname of the box
        :param stanza_names: array of string containing resource's stanza
        name be delete
        :return: None if all good, otherwise throw AppConfigException
        at the end
        '''

        failures = []
        client = self._get_client(hostname)
        for stanza_name in stanza_names:
            try:
                client.delete(endpoint, stanza_name)
            except Exception as e:
                failures.append([hostname, endpoint, stanza_name])
                logger.error('Failure', stanza=stanza_name, error=e.message)
            else:
                logger.info('Success', stanza=stanza_name)

        if failures:
            raise AppConfigException('Failed to delete', failures)

    def list(self, endpoint, hostname, stanza_names=None):
        '''
        List resource in a loop or list all resource specified

        :param endpoint: resource rest API endpoint
        :param hostname: hostname of the box
        :param stanza_names: array of string containing resource's stanza
        name be query. If it is None, then query all resources
        :return: array containing JSON object if all good,
        otherwise throw exception once it hits
        '''

        client = self._get_client(hostname)
        if not stanza_names:
            return client.list(endpoint)

        results = []
        for stanza_name in stanza_names:
            result = client.list(endpoint, stanza_name)
            if isinstance(result, list):
                results.extend(result)
            else:
                results.append(result)
        return results

    def _get_client(self, hostname):
        if hostname in self.app_clients:
            return self.app_clients[hostname]

        client = AppConfigClient(
            self.splunks[hostname], self.appname, self.owner)
        self.app_clients[hostname] = client

        return client
