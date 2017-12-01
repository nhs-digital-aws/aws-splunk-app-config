import splunk.admin as admin
from base_input_rh import BaseInputRestHandler

ARGS = [
    'aws_account',
    'aws_region',
    'index',
    'aws_iam_role',
    'metric_dimensions',
    'metric_names',
    'metric_namespace',
    'period',
    'polling_interval',
    'sourcetype',
    'statistics',
    'disabled'
]

GROUP_FIELDS = ['metric_dimensions', 'metric_names', 'metric_namespace', 'statistics']

class InputsProxyHandler(BaseInputRestHandler):
    def __init__(self, *args, **kwargs):
        self.opt_args = ARGS
        self.required_args = []
        self.group_fields = GROUP_FIELDS
        self.input_name = 'aws_cloudwatch'

        BaseInputRestHandler.__init__(
            self,
            *args,
            **kwargs
        )

        return


admin.init(InputsProxyHandler, admin.CONTEXT_APP_ONLY)
