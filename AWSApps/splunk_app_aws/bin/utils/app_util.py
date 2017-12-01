__author__ = 'michael'

import csv
import logging
import os
import logging.handlers as handlers
from splunklib.client import Entity, Service
from utils.local_manager import LocalServiceManager
from security_logging.security_logger import SecurityLogger

APP = 'saas_app_aws'

APP_NAME = 'splunk_app_aws'

AWS_ADMIN_CAPABILITY = 'aws_admin_capability'
VALIDATION_FAILED_MSG = 'AWS Admin Validation Failed.'

LOOKUP_REPLICATE_REST = 'data/lookup-table-files'
STAGING_FOLDER_PATH = os.path.join(os.environ.get('SPLUNK_HOME'), 'var', 'run', 'splunk', 'lookup_tmp')


def create_logger_handler(fd, level, max_bytes=10240000, backup_count=5):
    handler = handlers.RotatingFileHandler(fd, maxBytes=max_bytes, backupCount=backup_count)
    handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] [%(filename)s] %(message)s'))
    handler.setLevel(level)
    return handler


def get_logger(level=logging.INFO):
    logger = logging.Logger(APP)
    LOG_FILENAME = os.path.join(os.environ.get('SPLUNK_HOME'), 'var', 'log', 'splunk', '%s.log' % APP)
    logger.setLevel(level)
    handler = create_logger_handler(LOG_FILENAME, level)
    logger.addHandler(handler)
    # use adapter to avoid log injection attack
    logger_adapter = SecurityLogger(logger)
    return logger_adapter


def flatten_args(caller_args, separator=','):
    args = {}
    for k in caller_args:
        if isinstance(caller_args[k], list):
            v = filter(lambda x: x is not None, caller_args[k])
            if len(v) > 0:
                args[k] = separator.join(caller_args[k])
    return args


def get_option_from_conf(session_key, conf_name, stanza_name, option_name):
    service = LocalServiceManager(app=APP_NAME, session_key=session_key).get_local_service()
    conf = service.confs[conf_name]

    if stanza_name in conf:
        return conf[stanza_name].content[option_name]

    return None


def update_index_macro(session_key, stanza_name, index_name):
    service = LocalServiceManager(app=APP_NAME, session_key=session_key).get_local_service()
    macros_conf = service.confs['macros']

    if stanza_name not in macros_conf:
        get_logger().error('"%s" do not support in macros.conf' % stanza_name)
        return False

    macro_definition = macros_conf[stanza_name].content['definition']

    if macro_definition.find('"%s"' % index_name) == -1:
        new_macro_definition = macro_definition[0:len(macro_definition) - 1] + ' OR index="%s")' % index_name
        macros_conf[stanza_name].update(**{'definition': new_macro_definition})
        get_logger().info('"%s" successfully write in macros.conf' % stanza_name)
        return True

    return False


def validate_aws_admin(session_key):
    if not is_aws_admin(session_key):
        raise Exception(VALIDATION_FAILED_MSG)

    return


def is_aws_admin(session_key):
    service = LocalServiceManager(app=APP_NAME, session_key=session_key).get_local_service()

    # get capabilities and roles of current user
    current_context = Entity(service, 'authentication/current-context')
    user_capabilities = current_context.content['capabilities']
    user_roles = current_context.content['roles']

    # If there is "aws_admin_capability" capability, then user should have it
    if AWS_ADMIN_CAPABILITY in user_capabilities:
        return True

    # If it is Splunk-Cloud environment (not support customized capabilities), need to check "sc_admin" or "admin" role
    if 'sc_admin' in user_roles or 'admin' in user_roles:
        return True

    return False


def get_search_restrictions(session_key):
    service = LocalServiceManager(app=APP_NAME, session_key=session_key).get_local_service()

    # get current user roles
    current_user_roles = Entity(service, 'authentication/current-context').content['roles']

    # for the user roles that exist in the conf, append the search restriction
    search_restriction_arr = []
    for role in current_user_roles:
        search_restriction = Entity(service, 'authorization/roles/%s' % role).content['srchFilter']
        if search_restriction is not None:
            search_restriction_arr.append('(%s)' % search_restriction)

    return search_restriction_arr


def update_lookup_file(session_key, lookup_file_name, header, content):
    """
        Use rest to update lookup in consistent way
    :param session_key: session key
    :param lookup_file_name: updated look file name
    :param header: a list, like ['headerA','headerB','headerC']
    :param content: a list with each element is a dict, like [{'headerA':'a1','headerB':'b1','headerC':'c1'}, {'headerA':'a2','headerB':'b2','headerC':'c2'}]
    """
    if _write_tmp_lookup_file(lookup_file_name, header, content):
        _replicate_lookup_file(session_key, lookup_file_name)


def _write_tmp_lookup_file(lookup_file_name, header, content):
    get_logger().info('writing lookup file %s to staging folder' % lookup_file_name)

    try:
        if not os.path.isdir(STAGING_FOLDER_PATH):
            os.mkdir(STAGING_FOLDER_PATH)
        staging_file_path = os.path.join(STAGING_FOLDER_PATH, lookup_file_name)
        with open(staging_file_path, 'w+') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=header)
            writer.writeheader()
            for row in content:
                writer.writerow(row)

        get_logger().info('%s rows were written' % len(content))
        return True
    except:
        return False


def _replicate_lookup_file(session_key, lookup_file_name):
    get_logger().info('replicating lookup file %s' % lookup_file_name)

    service = LocalServiceManager(app=APP_NAME, session_key=session_key).get_local_service()
    lookup_file_path = os.path.abspath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'lookups', lookup_file_name))

    if os.path.isfile(lookup_file_path):
        get_logger().info('lookup file %s already exists, updating...' % lookup_file_name)
        service.post('%s/%s' % (LOOKUP_REPLICATE_REST, lookup_file_name), **{
            'eai:data': os.path.join(STAGING_FOLDER_PATH, lookup_file_name)
        })
    else:
        get_logger().info('lookup file %s not found, creating...' % lookup_file_name)
        service.post(LOOKUP_REPLICATE_REST, **{
            'eai:data': os.path.join(STAGING_FOLDER_PATH, lookup_file_name),
            'name': lookup_file_name
        })
