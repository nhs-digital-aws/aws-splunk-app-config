import aws_bootstrap_env
from splunktaucclib.rest_handler.endpoint import (
    field,
    validator,
    RestModel,
    DataInputModel,
)
from splunktaucclib.rest_handler import admin_external, util
from splunktaucclib.rest_handler.admin_external import AdminExternalHandler
import logging

util.remove_http_proxy_env_vars()


fields = [
    field.RestField(
        'aws_account',
        required=True,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'aws_iam_role',
        required=False,
        encrypted=False,
        default='',
        validator=None
    ), 
    field.RestField(
        'host_name',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'bucket_name',
        required=True,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'interval',
        required=False,
        encrypted=False,
        default=1800,
        validator=validator.Number(
            max_val=31536000, 
            min_val=0, 
        )
    ), 
    field.RestField(
        'log_type',
        required=True,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'log_file_prefix',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'log_start_date',
        required=False,
        encrypted=False,
        default=None,
        validator=validator.Pattern(
            regex=r"""^\d{4}-\d{2}-\d{2}$""", 
        )
    ), 
    field.RestField(
        'sourcetype',
        required=False,
        encrypted=False,
        default='aws:s3',
        validator=None
    ), 
    field.RestField(
        'index',
        required=True,
        encrypted=False,
        default='default',
        validator=None
    ), 
    field.RestField(
        'bucket_region',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'log_name_format',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'max_fails',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'max_number_of_process',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'max_number_of_thread',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'max_retries',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ), 

    field.RestField(
        'disabled',
        required=False,
        validator=None
    )

]
model = RestModel(fields, name=None)



endpoint = DataInputModel(
    'splunk_ta_aws_logs',
    model,
)


if __name__ == '__main__':
    logging.getLogger().addHandler(logging.NullHandler())
    admin_external.handle(
        endpoint,
        handler=AdminExternalHandler,
    )
