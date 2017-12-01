import aws_bootstrap_env

from botocore.exceptions import ClientError

import logging

import splunk.admin as admin

import splunk.clilib.cli_common as scc
from splunktalib.conf_manager.conf_manager import ConfManager
from splunk_ta_aws.common.aws_accesskeys import AwsAccessKeyManager

from splunktalib.rest_manager import util, error_ctl

from splunktaucclib.rest_handler.error import RestError

import splunk_ta_aws.common.ta_aws_consts as tac

import splunk_ta_aws.common.account_util as account_util

KEY_NAMESPACE = util.getBaseAppName()
KEY_OWNER = '-'

AWS_PROXY_PREFIX = "_aws_"

POSSIBLE_KEYS = ('secret_key', 'key_id')
OPTIONAL_KEYS = ('category', )
CONF_FOR_ACCOUNT_EXT_FIELDS = "aws_account_ext"


class AccountRestHandler(admin.MConfigHandler):
    """
    Manage AWS Accounts in Splunk_TA_aws add-on.
    """

    def setup(self):
        if self.requestedAction in (admin.ACTION_CREATE, admin.ACTION_EDIT):
            for arg in POSSIBLE_KEYS:
                self.supportedArgs.addReqArg(arg)
            for arg in OPTIONAL_KEYS:
                self.supportedArgs.addOptArg(arg)
        return

    def _getConfManager(self):
        sessionKey = self.getSessionKey()
        server_uri = scc.getMgmtUri()
        return ConfManager(server_uri, sessionKey, "nobody", KEY_NAMESPACE)

    def _getAccountConfig(self, key, exts):
        result = {
            'name': key.name,
            'key_id': key.key_id,
            'secret_key': key.secret_key,
            'category': key.category,
            'iam': key.iam,
            'token': key.token,
            'account_id': key.account_id,
        }
        temp = exts.get(key.name)
        if temp:
            for key in temp:
                if key in OPTIONAL_KEYS:
                    result[key] = temp[key]
            result['category'] = int(result['category'])
            if result['category'] not in tac.RegionCategory.VALID:
                result['category'] = tac.RegionCategory.DEFAULT
        elif result["iam"]:
            # create account for EC2 role in aws_account_ext.conf
            cm = self._getConfManager()
            account_ext = {
                "category": result["category"],
                "iam": 1,
            }
            cm.create_stanza(CONF_FOR_ACCOUNT_EXT_FIELDS, key.name, account_ext)

            # append this account into summary index
            if key['account_id'] and key['name']:
                account_util.append_account_to_summary(name=key['name'],
                                                       account_id=key['account_id'],
                                                       category=key['category'],
                                                       session_key=self.getSessionKey())

        return result

    def handleCreate(self, confInfo):
        try:
            self.callerArgs.id = self.callerArgs.id.strip()
            if self.callerArgs.id.lower() in ('default', ):
                raise RestError(
                    400,
                    'Name "%s" for AWS account is not allowed.' % self.callerArgs.id
                )

            accs = self.all()
            keys = {key.lower() for key in accs}
            if self.callerArgs.id.lower() in keys:
                raise Exception('An AWS account named \"%s\" already exists. Note: it is not case-sensitive.' % self.callerArgs.id)

            args = self.validate(self.callerArgs.data)
            km = AwsAccessKeyManager(KEY_NAMESPACE, KEY_OWNER, self.getSessionKey())
            km.set_accesskey(key_id=args['key_id'][0], secret_key=args['secret_key'][0], name=self.callerArgs.id)

            cm = self._getConfManager()
            cate = args['category'][0]

            if cm.stanza_exist(CONF_FOR_ACCOUNT_EXT_FIELDS, self.callerArgs.id):
                cm.delete_stanza(CONF_FOR_ACCOUNT_EXT_FIELDS, self.callerArgs.id)

            cm.create_stanza(CONF_FOR_ACCOUNT_EXT_FIELDS, self.callerArgs.id, {"category": cate})

            new_account = self.get(self.callerArgs.id)
            account_id = account_util.get_account_id(new_account, self.getSessionKey())

            account_util.append_account_to_summary(name=new_account['name'],
                                                   account_id=account_id,
                                                   category=new_account['category'],
                                                   session_key=self.getSessionKey())

        except Exception as exc:
            raise RestError(
                400,
                exc
            )

    def handleRemove(self, confInfo):
        try:
            km = AwsAccessKeyManager(KEY_NAMESPACE, KEY_OWNER, self.getSessionKey())
            km.delete_accesskey(self.callerArgs.id)

            cm = self._getConfManager()
            if cm.stanza_exist(CONF_FOR_ACCOUNT_EXT_FIELDS, self.callerArgs.id):
                cm.delete_stanza(CONF_FOR_ACCOUNT_EXT_FIELDS, self.callerArgs.id)
        except Exception as exc:
            raise RestError(
                400,
                exc
            )

    def handleEdit(self, confInfo):
        try:
            args = self.validate(self.callerArgs.data)
            account_name = self.callerArgs.id.strip()
            key_id = args['key_id'][0]
            secret_key = args['secret_key'][0]
            category = args['category'][0]

            session_key = self.getSessionKey()

            # check whether the updated one belongs to another account ID
            old_account_id = None

            try:
                old_account = self.get(account_name)
                old_account_id = account_util.get_account_id(old_account, session_key)
            except ClientError:
                pass

            new_account_id = account_util.get_account_id({
                'key_id': key_id,
                'secret_key': secret_key,
                'category': category
            }, session_key)

            if old_account_id is not None and old_account_id != new_account_id:
                raise Exception("Failed in updating AWS account. You can not update the account with a different root account ID.")

            km = AwsAccessKeyManager(KEY_NAMESPACE, KEY_OWNER, session_key)
            km.set_accesskey(key_id=key_id, secret_key=secret_key, name=account_name)

            cm = self._getConfManager()

            if cm.stanza_exist(CONF_FOR_ACCOUNT_EXT_FIELDS, account_name):
                cm.update_stanza(CONF_FOR_ACCOUNT_EXT_FIELDS, account_name, {'category': category})
            else:
                cm.create_stanza(CONF_FOR_ACCOUNT_EXT_FIELDS, account_name, {'category': category})

            # The old account is invalid. It means the secret key and key ID is invalid for the old one. The new account needs to be appended into the summary index.
            if old_account_id is None:
                account_util.append_account_to_summary(name=account_name,
                                                       account_id=new_account_id,
                                                       category=category,
                                                       session_key=self.getSessionKey())

        except Exception as exc:
            raise RestError(
                400,
                exc
            )

    def handleList(self, confInfo):
        try:
            if self.callerArgs.id is None:
                accs = self.all()
                for name, ent in accs.items():
                    self.makeConfItem(name, ent, confInfo)
            else:
                self.makeConfItem(self.callerArgs.id, self.get(self.callerArgs.id), confInfo)
        except Exception as exc:
            raise RestError(
                400,
                exc
            )

    def validate(self, args):
        try:
            args['key_id'][0] = args['key_id'][0].strip()
            if len(args['key_id'][0]) <= 0:
                raise Exception('')
        except:
            error_ctl.RestHandlerError.ctl(1100, msgx='key_id', logLevel=logging.INFO)

        try:
            args['secret_key'][0] = args['secret_key'][0].strip()
            if len(args['secret_key'][0]) <= 0:
                raise Exception('')
        except:
            error_ctl.RestHandlerError.ctl(1100, msgx='secret_key', logLevel=logging.INFO)

        try:
            cate = args['category'][0] = int(args['category'][0])
            if cate not in tac.RegionCategory.VALID:
                raise Exception('')
        except:
            error_ctl.RestHandlerError.ctl(1100, msgx='category', logLevel=logging.INFO)

        # validate keys, category
        if not account_util.validate_keys(self.getSessionKey(),
                                          key_id=args['key_id'][0],
                                          secret_key=args['secret_key'][0],
                                          category=args['category'][0]):
            raise Exception('The account key ID, secret key or category is invalid. Please check.')

        return args

    def all(self):
        km = AwsAccessKeyManager(KEY_NAMESPACE, KEY_OWNER, self.getSessionKey())
        keys = km.all_accesskeys()
        all_accounts = {}
        all_accounts_exts = None
        for key in keys:
            if all_accounts_exts is None:
                cm = self._getConfManager()
                all_accounts_exts = cm.all_stanzas_as_dicts(CONF_FOR_ACCOUNT_EXT_FIELDS)
            if str(key.name).lower().startswith(AWS_PROXY_PREFIX):
                continue
            all_accounts[key.name] = self._getAccountConfig(key, all_accounts_exts)
        return all_accounts

    def get(self, name):
        name = name.strip()
        km = AwsAccessKeyManager(KEY_NAMESPACE, KEY_OWNER, self.getSessionKey())
        key = km.get_accesskey(name)
        if key is None:
            raise Exception('No AWS account named \"%s\" exists.' % (name))
        cm = self._getConfManager()
        exts = cm.all_stanzas_as_dicts(CONF_FOR_ACCOUNT_EXT_FIELDS, do_reload=False)
        return self._getAccountConfig(key, exts)

    def makeConfItem(self, name, entity, confInfo):
        confItem = confInfo[name]
        for key, val in entity.items():
            confItem[key] = val
        confInfo[name]['eai:appName'] = KEY_NAMESPACE
        confInfo[name]['eai:userName'] = 'nobody'
        confItem.setMetadata(
            admin.EAI_ENTRY_ACL,
            {'app': KEY_NAMESPACE, 'owner': 'nobody'},
        )


if __name__ == "__main__":
    admin.init(AccountRestHandler, admin.CONTEXT_APP_AND_USER)
