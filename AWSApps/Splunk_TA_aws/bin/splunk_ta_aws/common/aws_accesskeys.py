"""
This should probably be rewritten to just use SplunkAppObjModel directly...
"""


import re
import traceback
import requests

APPNAME = 'Splunk_TA_aws'
KEY_NAMESPACE = APPNAME
KEY_OWNER = '-'

from credentials_manager import CredentialManager

import boto.utils as bu
import splunk.clilib.cli_common as scc
import splunktalib.splunk_cluster as sc

from splunksdc import logging


logger = logging.get_module_logger()


def extract_region_category(role_info):
    placement = role_info.get("placement")
    category = ""
    if placement:
        az = placement.get("availability-zone", "")
        if "cn-north" in az:
            category = 4
        elif "us-gov" in az:
            category = 2
        else:
            category = 1
    return category


def extract_account_id(role_info):
    arn = role_info["iam"]["info"]["InstanceProfileArn"]
    # arn:aws(-cn):iam::012233333330:instance-profile/dummy-ec2-iam
    m = re.search(r"iam:.*:(\d+):", arn)
    if m:
        return m.group(1)
    else:
        return "0" * 12


def get_ec2_iam_role_creds():
    try:
        role_info = bu.get_instance_metadata(
            timeout=2, num_retries=1)
        # IAM role not found
        if 'iam' not in role_info:
            logger.debug('IAM role for EC2 instance not found')
            return None

        name, cred = role_info["iam"]["security-credentials"].items()[0]

        # Check credentials in returning result
        req_fields = ('AccessKeyId', 'SecretAccessKey', 'Token')
        if not all(cred.get(f) for f in req_fields):
            msg = 'Failed to get EC2 IAM role credentials.' \
                  ' Message={}. Code={}.'.format(
                    cred.get('Message'), cred.get('Code'))
            logger.error(msg)
            return None

        cred["RegionCategory"] = extract_region_category(role_info)
        cred["Name"] = name
        cred["AccountId"] = extract_account_id(role_info)
        return cred
    except Exception:
        msg = 'Failed to get EC2 IAM role credentials. {}'.format(
            traceback.format_exc()
        )
        logger.error(msg)
        return None


class AwsAccessKey(object):

    def __init__(self, key_id, secret_key, name="default",
                 region_category=0, token="", account_id="", is_iam=0):
        self.name = name
        self.key_id = key_id and key_id.strip() or ''
        self.secret_key = secret_key and secret_key.strip() or ''
        self.category = region_category
        self.token = token
        self.iam = is_iam
        self.account_id = account_id


class AwsAccessKeyManager(object):

    def __init__(self, namespace, owner, session_key):
        self.namespace = namespace
        self.owner = owner
        self._session_key = session_key
        self._cred_mgr = CredentialManager(sessionKey=session_key)

    def set_accesskey(self, key_id, secret_key, name='default'):
        if name is None:
            name = ''
        # create_or_set() will raise if empty username or password strings are passed
        key_id = key_id and key_id.strip() or ' '
        secret_key = secret_key and secret_key.strip() or ' '
        c = self.get_accesskey(name)
        if c and c.key_id != key_id:
            self.delete_accesskey(name)
        self._cred_mgr.create_or_set(key_id, name, secret_key, self.namespace, self.owner)

    def get_accesskey(self, name='default'):
        keys = self.all_accesskeys()
        for key in keys:
            if key.name == name:
                return key
        else:
            return None

    def all_accesskeys(self):
        class AccessKeyIterator(object):

            def __init__(self, mgr):
                self.creds = mgr._cred_mgr.all().filter_by_app(mgr.namespace).filter_by_user(mgr.owner)
                self._session_key = mgr._session_key

            def __iter__(self):
                for c in self.creds:
                    if c.realm.startswith('__REST_CREDENTIAL__#'):
                        continue

                    yield AwsAccessKey(c.username, c.clear_password, c.realm)

                try:
                    requests.get('http://169.254.169.254/latest/meta-data/', timeout=2)
                except IOError:
                    logger.debug('Not running on EC2 instance, skip instance role discovery.')
                    raise StopIteration()

                server_info = sc.ServerInfo(scc.getMgmtUri(), self._session_key)
                if not server_info.is_cloud_instance():
                    cred = get_ec2_iam_role_creds()
                    if cred:
                        yield AwsAccessKey(
                            cred["AccessKeyId"], cred["SecretAccessKey"],
                            cred["Name"], cred["RegionCategory"],
                            cred["Token"], cred["AccountId"], 1)

        return AccessKeyIterator(self)

    def delete_accesskey(self, name='default'):
        if name is None:
            name = ''
        c = self.get_accesskey(name)
        if c:
            self._cred_mgr.delete(c.key_id, c.name, self.namespace, self.owner)
