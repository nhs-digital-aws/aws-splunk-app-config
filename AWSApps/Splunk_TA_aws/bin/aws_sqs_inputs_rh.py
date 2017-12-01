import splunk.admin as admin
from base_input_rh import BaseInputRestHandler

ARGS = [
    'aws_account',
    'aws_iam_role',
    'aws_region',
    'sqs_queues',
    'sourcetype',
    'interval',
    'index',
    'disabled'
]

GROUP_FIELDS = ['aws_region', 'sqs_queues']

class InputsProxyHandler(BaseInputRestHandler):
    def __init__(self, *args, **kwargs):
        self.opt_args = ARGS
        self.required_args = []
        self.group_fields = GROUP_FIELDS
        self.input_name = 'splunk_ta_aws_sqs'
        self.origin_endpoint = 'aws_sqs_inputs_rh_ucc'

        BaseInputRestHandler.__init__(
            self,
            *args,
            **kwargs
        )

        return


admin.init(InputsProxyHandler, admin.CONTEXT_APP_ONLY)
