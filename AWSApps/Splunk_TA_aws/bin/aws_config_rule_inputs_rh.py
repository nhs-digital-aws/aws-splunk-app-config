import splunk.admin as admin
from base_input_rh import BaseInputRestHandler

ARGS = [
    'account',
    'aws_iam_role',
    'region',
    'rule_names',
    'polling_interval',
    'sourcetype',
    'index',
    'disabled'
]

GROUP_FIELDS = ['region', 'rule_names']

class InputsProxyHandler(BaseInputRestHandler):
    def __init__(self, *args, **kwargs):
        self.opt_args = ARGS
        self.required_args = []
        self.group_fields = GROUP_FIELDS
        self.input_name = 'aws_config_rule'

        BaseInputRestHandler.__init__(
            self,
            *args,
            **kwargs
        )

        return


admin.init(InputsProxyHandler, admin.CONTEXT_APP_ONLY)
