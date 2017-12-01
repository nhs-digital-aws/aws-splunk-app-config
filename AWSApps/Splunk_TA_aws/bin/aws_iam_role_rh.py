import aws_bootstrap_env

import splunk.admin as admin
from splunktalib.rest_manager import base, validator

import splunk_ta_aws.common.account_util as account_util


class IAMRole(base.BaseModel):
    endpoint = "configs/conf-splunk_ta_aws_iam_roles"
    requiredArgs = {'arn'}
    encryptedArgs = {'arn'}
    validators = {
        'arn': validator.Pattern(
            '^arn:[^\s:]+:iam::\d+:role(:|/)[^/:\s]+$')
    }


class IAMHandler(base.BaseRestHandler):

    def handleEdit(self, confInfo):
        super(IAMHandler, self).handleEdit(confInfo)
        self._append_to_summary()


    def handleCreate(self, confInfo):
        super(IAMHandler, self).handleCreate(confInfo)
        self._append_to_summary()


    def _append_to_summary(self):
        role_name = self.callerArgs.id
        role_arn = self.callerArgs.data['arn'][0]
        account_util.append_assume_role_to_summary(name=role_name, arn=role_arn, session_key=self.getSessionKey())


    # override handler name, as the cred_mgmt.py uses handler name as a part of the password realm (which is a bad as well as legacy design)
    def _getHandlerName(self):
        return 'BaseRestHandler'


if __name__ == "__main__":
    admin.init(
        base.ResourceHandler(IAMRole, handler=IAMHandler),
        admin.CONTEXT_APP_AND_USER,
    )