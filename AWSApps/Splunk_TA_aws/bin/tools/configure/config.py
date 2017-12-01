import json
import os.path as op
import glob

import splunklib.client as sc
import solnlib.utils as sutils
import splunksdc.log as logging

logger = logging.get_context_logger('configuration_tool')


class SplunkInfo(object):

    def __init__(self, splunk):
        self.validate(splunk)
        self.hostname = splunk['hostname']
        self.mgmt_uri = splunk['mgmt_uri']
        self.username = splunk['username']
        self.password = splunk['password']
        self.session_key = splunk.get('session_key')

    @staticmethod
    def validate(splunk):
        if not isinstance(splunk, dict):
            logger.error(
                'Invalid splunk-info file. Expect splunk as a dict object',
                got=splunk)
            raise ValueError('Invalid splunk-info file')

        requires = ['hostname', 'mgmt_uri', 'username', 'password']
        check_required(splunk, requires, 'Invalid splunk-info file')

        scheme, host, port = sutils.extract_http_scheme_host_port(
            splunk["mgmt_uri"])
        # Verify username, password, and mgmt_uri
        try:
            sc.connect(scheme=scheme, host=host, port=port,
                       username=splunk['username'],
                       password=splunk['password'])
        except Exception as e:
            logger.error('Invalid splunk-info file, credentials or URI are '
                         'probably wrong', error=e.message)
            raise ValueError('Invalid splunk-info file')


class RestStanzaField(object):

    def __init__(self, field):
        self.validate(field)
        self.name = field['name']
        self.required = field['required']
        self.description = field.get('description')

    @staticmethod
    def validate(field):
        if not isinstance(field, dict):
            logger.error('Invalid rest API spec, expect stanza_field as dict',
                         got=field)
            raise ValueError('Invalid rest API spec')

        requires = ['name', 'required']
        check_required(field, requires, 'Invalid rest API spec')


class RestAPISpec(object):

    def __init__(self, spec):
        self.validate(spec)
        self.name = spec['name']
        self.endpoint = spec['endpoint']
        self.stanza_fields = [
            RestStanzaField(field) for field in spec['stanza_fields']]

    @staticmethod
    def validate(spec):
        requires = ['name', 'endpoint', 'stanza_fields']
        check_required(spec, requires, 'Invalid rest API spec')

        if not isinstance(spec['stanza_fields'], list):
            logger.error('Invalid rest API spec, expect list stanza_fields',
                         got=spec['stanza_fields'])
            raise ValueError('Invalid rest API spec')


class HostStanza(object):

    def __init__(self, host_stanza, **kwargs):
        self.validate(host_stanza, **kwargs)
        self.rest_endpoint_name = host_stanza['rest_endpoint_name']
        self.hostname = host_stanza['hostname']
        self.stanzas = host_stanza['stanzas']
        self.rest_endpoint = None

    @staticmethod
    def validate(host_stanza, **kwargs):
        if not isinstance(host_stanza, dict):
            logger.error(
                'Invalid config file. Expect stanza as a dict object',
                got=host_stanza)
            raise ValueError('Invalid config file')

        for k in ['rest_endpoint_name', 'hostname']:
            if kwargs.get(k):
                # If client pass in the endpoint name or hostname, then it is
                # not required rest_endpoint_name/hostname in conf file.
                host_stanza[k] = kwargs[k]

        requires = ['rest_endpoint_name', 'hostname', 'stanzas']
        check_required(host_stanza, requires, 'Invalid config file')

        rest_stanzas = host_stanza.get('stanzas')
        if not isinstance(rest_stanzas, list):
            logger.error(
                'Invalid config file. Expect list of stanzas',
                got=rest_stanzas)
            raise ValueError('Invalid config file')

        for stanza in rest_stanzas:
            check_required(stanza, ['name'], 'Invalid config file')


def check_required(dict_obj, requires, msg):
    for required in requires:
        if required not in dict_obj or dict_obj[required] in (None, ''):
            logger.error(msg, required=required)
            raise ValueError(msg)


def load_rest_api_specs(spec_dir):
    '''
    Load rest API spec information from directory and do necessary validation

    :param spec_dir: Directory name contains rest API spec files whose name
    ends with .spec
    :return: a dict of `RestAPISpec` objects when successful,
    otherwise raise Exception
    '''

    if not op.exists(spec_dir):
        logger.error(
            'Didn\'t find `rest_specs` directory. Need config that '
            'first', rest_spec_dir=spec_dir)
        raise ValueError('rest_specs is not found')

    api_specs = {}
    for spec_file in glob.glob(op.join(spec_dir, '*.spec')):
        try:
            spec = get_one_spec(spec_file)
        except ValueError:
            continue

        if spec.name in api_specs:
            logger.warn(
                'rest API spec with the same name, will override previous one',
                spec_file=spec_file, name=spec.name)
        api_specs[spec.name] = spec
    return api_specs


def get_one_spec(spec_file):
    with logging.LogContext(spec_file=spec_file):
        return _do_get_spec(spec_file)


def _do_get_spec(spec_file):
    with open(spec_file) as fp:
        try:
            spec = json.load(fp)
        except ValueError as e:
            logger.error("Invalid rest API spec. Invalid json")
            raise e

    return RestAPISpec(spec)


def load_configs(config_file, splunks, rest_api_specs, **kwargs):
    '''
    Load stanzas information information from file and do necessary validation

    :param config_file: file name which contains stanzas information which are
    used to create resource
    :params kwargs: client can pass in 2 additional params for now
      1. rest_endpoint_name
      2. hostname
      when client passed in these 2 params, it will override the settings
      in conf.
    :return: a list of `HostStanza` object when successful,
    otherwise raise Exception
    '''

    with logging.LogContext(config_file=config_file):
        return _do_load_configs(
            config_file, splunks, rest_api_specs, **kwargs)


def _do_load_configs(config_file, splunks, rest_api_specs, **kwargs):
    with open(config_file) as fp:
        try:
            host_stanzas = json.load(fp)
        except ValueError as e:
            logger.error(
                'Invalid config file. Invalid json')
            raise e

    if not isinstance(host_stanzas, list):
        logger.error(
            'Invalid config file. Expect list of stanzas', got=host_stanzas)
        raise ValueError('Invalid config file')

    host_stanzas = [
        HostStanza(host_stanza, **kwargs) for host_stanza in host_stanzas]

    # External validation
    for host_stanza in host_stanzas:
        _validate_one_host_stanza(host_stanza, splunks, rest_api_specs)

    return host_stanzas


def _validate_one_host_stanza(host_stanza, splunks, rest_api_specs):
    '''
    External validation against `SplunkInfo` and `RestAPISpec`
    '''

    if host_stanza.rest_endpoint_name not in rest_api_specs:
        logger.error(
            'Invalid config file. Invalid rest endpoint name',
            rest_endpoint_name=host_stanza.rest_endpoint_name,
            valid=rest_api_specs.keys())
        raise ValueError('Invalid config file')

    # Attach `endpoint` to `host_stanza` to avoid passing around rest API
    # specs
    spec = rest_api_specs[host_stanza.rest_endpoint_name]
    host_stanza.rest_endpoint = spec.endpoint

    if host_stanza.hostname not in splunks:
        logger.error(
            'Invalid config file. hostname is not configured in splunk-info',
            hostname=host_stanza.hostname, valid=splunks.keys())
        raise ValueError('Invalid config file')

    _validate_host_stanza_against_rest_specs(host_stanza, rest_api_specs)


def _validate_host_stanza_against_rest_specs(host_stanza, rest_api_specs):
    '''
    External validation against `RestAPISpec`
    '''

    spec = rest_api_specs[host_stanza.rest_endpoint_name]
    valid_keys = {field.name: field.required for field in spec.stanza_fields}

    for stanza in host_stanza.stanzas:
        # Verify the key specified in stanza is valid
        for key in stanza.iterkeys():
            if key == 'name':
                continue

            if key in valid_keys:
                continue

            logger.error(
                'Invalid config file. Invalid key in stanza',
                rest_endpoint_name=host_stanza.rest_endpoint_name,
                invalid_key=key, valid_keys=valid_keys.keys())
            raise ValueError('Invalid config file')

        # Verify required key in spec have been specified in stanza
        for key, required in valid_keys.iteritems():
            if not required:
                continue

            if key in stanza:
                continue

            logger.error(
                'Invalid config file. Missing required key in stanza',
                rest_endpoint_name=host_stanza.rest_endpoint_name,
                required=key)
            raise ValueError('Invalid config file')


def load_splunks(splunk_info_file):
    '''
    Load splunk information from file and do necessary validation

    :param splunk_info_file: file name contains Splunk credetial etc in
    formation in a JSON array.
    :return: a dict of `SplunkInfo` objects by hostname as the key when
    successful, otherwise raise Exception
    '''

    with logging.LogContext(splunk_info=splunk_info_file):
        return _do_load_splunks(splunk_info_file)


def _do_load_splunks(splunk_info_file):
    if not op.exists(splunk_info_file):
        logger.error(
            'Didn\'t find `splunk-info.json`. Need config that first',
            splunk_info_file=splunk_info_file)
        raise ValueError('splunk-info.json is not found')

    with open(splunk_info_file) as fp:
        try:
            splunks = json.load(fp)
        except ValueError as e:
            logger.error(
                'Invalid splunk-info file. Invalid json')
            raise e

    if not isinstance(splunks, list):
        logger.error(
            'Invalid splunk-info file. Expect list of splunk info', got=splunks)
        raise ValueError('Invalid splunk-info file')

    splunks = [SplunkInfo(splunk) for splunk in splunks]
    return {splunk.hostname: splunk for splunk in splunks}
