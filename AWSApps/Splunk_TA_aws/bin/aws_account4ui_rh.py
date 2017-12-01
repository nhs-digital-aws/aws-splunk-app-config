import aws_bootstrap_env

from splunk import admin
from splunktaucclib.rest_handler.error import RestError
from aws_account_rh import AccountRestHandler


class Account4UIRestHandler(AccountRestHandler):
    """
    Manage AWS Accounts in Splunk_TA_aws add-on for UI widgets.
    """
    def handleList(self, confInfo):
        try:
            if self.callerArgs.id is None:
                accs = self.all()
                for name, ent in accs.items():
                    self.makeConfItem(name, self.skip_cred(ent), confInfo)
            else:
                self.makeConfItem(
                    self.callerArgs.id,
                    self.skip_cred(self.get(self.callerArgs.id)),
                    confInfo,
                )
        except Exception as exc:
            raise RestError(
                400,
                exc
            )

    def skip_cred(self, ent):
        CRED_KEYS = ('secret_key', 'token')
        for key in CRED_KEYS:
            if key in ent:
                del ent[key]
        return ent

if __name__ == "__main__":
    admin.init(Account4UIRestHandler, admin.CONTEXT_APP_AND_USER)
