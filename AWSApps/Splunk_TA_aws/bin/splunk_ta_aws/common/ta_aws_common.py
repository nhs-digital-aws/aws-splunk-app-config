import sys
import time
import dateutil.tz.tz as dtt
import copy
import json
import urllib2
from splunk_ta_aws.common import boto3_proxy_patch
import boto3
import threading
from datetime import datetime, timedelta

# FIXME Legacy code started
import splunk_ta_aws.common.aws_accesskeys as taa
# Legacy code done

import splunklib.client
import splunktalib.common.util as scutil
import splunktalib.modinput as mi
from splunktalib.common import log
import splunktalib.hec_config as shc
import splunktalib.conf_manager.conf_manager as cm
from splunktalib.rest import splunkd_request
from splunklib.client import Service
from splunksdc.config import ConfigManager
import splunk_ta_aws.common.ta_aws_consts as tac
from splunk_ta_aws.common.aws_credentials import AWSCredentialsService
from urlparse import urlparse


boto3.setup_default_session()
boto3.DEFAULT_SESSION._session.get_component("data_loader")
boto3.DEFAULT_SESSION._session.get_component("event_emitter")
boto3.DEFAULT_SESSION._session.get_component("endpoint_resolver")
boto3.DEFAULT_SESSION._session.get_component("credential_provider")

def get_service_client(config, service):
    credentials = load_credentials_from_cache(
        config[tac.server_uri],
        config[tac.session_key],
        config[tac.aws_account],
        config.get(tac.aws_iam_role),
    )
    client = boto3.client(
        service,
        region_name=config[tac.region],
        aws_access_key_id=credentials.aws_access_key_id,
        aws_secret_access_key=credentials.aws_secret_access_key,
        aws_session_token=credentials.aws_session_token
    )
    return client, credentials


def validate_config():
    """
    Validate inputs.conf
    """

    return 0


def usage():
    """
    Print usage of this binary
    """

    hlp = "%s --scheme|--validate-arguments|-h"
    print >> sys.stderr, hlp % sys.argv[0]
    sys.exit(1)


def print_scheme(title, description):
    """
    Feed splunkd the TA's scheme
    """

    print """
    <scheme>
    <title>{title}</title>
    <description>{description}</description>
    <use_external_validation>true</use_external_validation>
    <streaming_mode>xml</streaming_mode>
    <use_single_instance>true</use_single_instance>
    <endpoint>
      <args>
        <arg name="name">
          <title>Unique name which identifies this data input</title>
        </arg>
        <arg name="placeholder">
          <title>placeholder</title>
        </arg>
      </args>
    </endpoint>
    </scheme>""".format(title=title, description=description)


def main(scheme_printer, run):
    args = sys.argv
    if len(args) > 1:
        if args[1] == "--scheme":
            scheme_printer()
        elif args[1] == "--validate-arguments":
            sys.exit(validate_config())
        elif args[1] in ("-h", "--h", "--help"):
            usage()
        else:
            usage()
    else:
        # sleep 5 seconds to wait KVStore ready
        time.sleep(5)
        run()


def setup_signal_handler(loader, logger):
    """
    Setup signal handlers
    @data_loader: data_loader.DataLoader instance
    """

    def _handle_exit(signum, frame):
        logger.info("Exit signal received, exiting...")
        loader.tear_down()

    scutil.handle_tear_down_signals(_handle_exit)


def get_file_change_handler(loader, logger):
    def reload_and_exit(changed_files):
        logger.info("Conf file(s)=%s changed, exiting...", changed_files)
        loader.tear_down()

    return reload_and_exit


def get_configs(ConfCls, modinput_name, logger):
    conf = ConfCls()
    tasks = conf.get_tasks()

    if not tasks:
        logger.info(
            "Not data collection tasks for %s is discovered. "
            "Doing nothing and quitting the TA.", modinput_name)
        return None, None, None

    return conf.metas, conf.stanza_configs, tasks


# ######## AWS ##########


def connect_service_to_region(api, config):
    conn = api(
        config[tac.region], aws_access_key_id=config.get(tac.key_id),
        aws_secret_access_key=config.get(tac.secret_key),
        security_token=config.get('aws_session_token'),
        proxy=config.get(tac.proxy_hostname),
        proxy_port=config.get(tac.proxy_port),
        proxy_user=config.get(tac.proxy_username),
        proxy_pass=config.get(tac.proxy_password),
        is_secure=True)

    return conn


DEFAULT_ID = "000000000000"


def parse_datetime(splunk_uri, session_key, time_str):
    """
    Leverage splunkd to do time parseing,
    :time_str: ISO8601 format, 2011-07-06T21:54:23.000-07:00
    """

    if not time_str:
        return None

    scheme, host, port = tuple(splunk_uri.replace("/", "").split(":"))

    service = splunklib.client.Service(token=session_key, scheme=scheme,
                                       host=host, port=port)
    endpoint = splunklib.client.Endpoint(service, "search/timeparser/")
    r = endpoint.get(time=time_str, output_time_format="%s")
    response = splunklib.data.load(r.body.read()).response
    seconds = response[time_str]
    return datetime.utcfromtimestamp(float(seconds))


def get_interval(task, default_interval):
    if task.get(tac.polling_interval):
        return int(task[tac.polling_interval])
    elif task.get(tac.interval):
        return int(task[tac.interval])
    return 3600


def get_modinput_configs():
    modinput = sys.stdin.read()
    meta, configs = mi.parse_modinput_configs(modinput)


    # Fix ADDON-12388.
    for config in configs:
        for key, val in config.iteritems():
            if isinstance(val, basestring):
                config[key] = val.strip()

    return meta, configs


def get_aws_creds(stanza, metas, creds):
    account_name = stanza.get(tac.aws_account)
    mgr = cm.ConfManager(
        metas[tac.server_uri], metas[tac.session_key],
        "nobody", "Splunk_TA_aws")
    ext_info = mgr.get_stanza("aws_account_ext", account_name)

    if not account_name or scutil.is_true(ext_info.get("iam")):
        # IAM role EC2
        key_id, secret_key = None, None
    else:
        if account_name in creds:
            key_id, secret_key = creds[account_name]
        else:
            km = taa.AwsAccessKeyManager(taa.KEY_NAMESPACE, taa.KEY_OWNER,
                                         metas[tac.session_key])

            acct = km.get_accesskey(name=account_name)
            if not acct:
                raise Exception("Failed to get creds for account=%s",
                                account_name)
            key_id, secret_key = acct.key_id, acct.secret_key
            creds[account_name] = [key_id, secret_key]
    return key_id, secret_key


def assert_creds(account_name, session_key, logger):
    import splunk.clilib.cli_common as scc

    stanza = {tac.aws_account: account_name}
    metas = {
        tac.server_uri: scc.getMgmtUri(),
        tac.session_key: session_key
    }

    key_id, secret_key = get_aws_creds(stanza, metas, {})
    if not key_id:
        mgr = cm.ConfManager(
            metas[tac.server_uri], session_key, "nobody", "Splunk_TA_aws")
        ext_info = mgr.get_stanza("aws_account_ext", account_name)
        if scutil.is_false(ext_info.get("iam")):
            logger.error("No AWS Account is configured. Setup App first.")
            raise Exception("No AWS Account is configured. Setup App first.")
    return key_id, secret_key


def sleep_until(interval, condition):
    """
    :interval: integer
    :condition: callable to check if need break the sleep loop
    :return: True when during sleeping condition is met, otherwise False
    """

    for _ in range(interval):
        time.sleep(1)
        if condition():
            return True
    return False


def is_http_ok(response):
    return response["ResponseMetadata"]["HTTPStatusCode"] in (200, 201)


def http_code(response):
    return response["ResponseMetadata"]["HTTPStatusCode"]


def total_seconds(date_with_dateutil_tz):
    epoch_time = datetime.utcfromtimestamp(0)
    epoch_time = epoch_time.replace(tzinfo=dtt.tzutc())
    return (date_with_dateutil_tz - epoch_time).total_seconds()


def set_proxy_env(config):
    if not config.get(tac.proxy_hostname):
        return

    username = config.get(tac.proxy_username)
    password = config.get(tac.proxy_password)
    hostname = config[tac.proxy_hostname]
    port = config[tac.proxy_port]
    url = assemble_proxy_url(hostname, port, username, password)
    boto3_proxy_patch.set_proxies("http://" + url, "https://" + url)


def handle_hec(tasks, hec_name):
    if not tasks:
        return

    config = copy.copy(tasks[0])
    config["hec_name"] = hec_name
    hec_input = shc.update_or_create_hec(config)
    keys = ["index", "name"]
    for task in tasks:
        with scutil.save_and_restore(task, keys):
            task.update(hec_input)
    return tasks


def assemble_proxy_url(hostname, port, username=None, password=None):
    endpoint = '{host}:{port}'.format(
        host=hostname,
        port=port
    )
    auth = None
    if username:
        auth = urllib2.quote(username.encode(), safe='')
        if password:
            auth += ':'
            auth += urllib2.quote(password.encode(), safe='')

    if auth:
        return auth + '@' + endpoint
    return endpoint


def make_splunkd_uri(scheme, host, port):
    return '{scheme}://{host}:{port}' \
           ''.format(scheme=scheme, host=host, port=port)


def make_splunk_endpoint(splunkd_uri, endpoint, user='nobody', app='-'):
    """
    Make full url for splunk endpoint.
    :param splunkd_uri:
    :param endpoint:
    :param user:
    :param app:
    :return:
    """
    endpoint = '/'.join(
        [splunkd_uri.strip('/'), 'servicesNS', user, app, endpoint.strip('/')])
    return endpoint + '?output_mode=json&count=0'


def load_config(url, session_key, config_label):
    """
    Get AWS configuration.

    :param url:
    :param session_key:
    :param config_label:
    :return:
    """
    resp, cont = splunkd_request(url, session_key, retry=3)
    if resp is None or resp.status not in (200, '200'):
        raise Exception('Fail to load %s - %s' % (config_label, cont))
    cont = json.loads(cont)
    return {ent['name']: ent['content'] for ent in cont['entry']}


def _build_config(splunkd_uri, session_key):
    splunkd_info = urlparse(splunkd_uri)
    service = Service(
        scheme=splunkd_info.scheme,
        host=splunkd_info.hostname,
        port=splunkd_info.port,
        token=session_key,
        owner='nobody',
        app='Splunk_TA_aws',
    )
    config = ConfigManager(service)

    return config


def create_credentials_service(splunkd_uri, session_key):
    config = _build_config(splunkd_uri, session_key)
    return AWSCredentialsService.create(config)


def get_account(splunkd_uri, session_key, account_name):
    """
    Fetch an account from conf. Used by rest handlers.
    Noticed that the returned account won't have arn, aws_session_token and etc.
    """
    config = _build_config(splunkd_uri, session_key)
    accounts = AWSCredentialsService.load_accounts(config)

    return accounts[account_name]


class AWSCredentialsCache(object):
    _cache = dict()
    _lock = threading.Lock()
    _service = None

    @classmethod
    def load_from_cache(
            cls,
            splunk_uri,
            session_key,
            aws_account_name,
            aws_iam_role_name=None
    ):
        with cls._lock:
            if cls._service is None:
                cls._service = create_credentials_service(splunk_uri, session_key)

            threshold = timedelta(minutes=15)
            key = (aws_account_name, aws_iam_role_name)
            if key in cls._cache:
                credentials = cls._cache[key]
                if not credentials.need_retire(threshold):
                    return credentials

            credentials = cls._service.load(aws_account_name, aws_iam_role_name)
            cls._cache[key] = credentials
            return credentials


def load_credentials_from_cache(
        splunk_uri,
        session_key,
        aws_account_name,
        aws_iam_role_name=None
):
    return AWSCredentialsCache.load_from_cache(
        splunk_uri,
        session_key,
        aws_account_name,
        aws_iam_role_name
    )


def update_boto2_connection(connection, credentials):
    """
    Update credentials for AWS connection of boto2.
    :param connection: boto2 connection
    :param credentials: base.aws_credentials.AWSCredentials
    :return:
    """
    provider = connection.provider
    provider.access_key = credentials.aws_access_key_id
    provider.secret_key = credentials.aws_secret_access_key
    provider.security_token = credentials.aws_session_token

