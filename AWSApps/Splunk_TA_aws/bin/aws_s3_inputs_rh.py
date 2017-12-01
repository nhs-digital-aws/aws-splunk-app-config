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
        'polling_interval',
        required=False,
        encrypted=False,
        default=1800,
        validator=validator.Number(
            max_val=31536000, 
            min_val=0, 
        )
    ), 
    field.RestField(
        'key_name',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'initial_scan_datetime',
        required=False,
        encrypted=False,
        default=None,
        validator=validator.Pattern(
            regex=r"""^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$""", 
        )
    ), 
    field.RestField(
        'terminal_scan_datetime',
        required=False,
        encrypted=False,
        default='',
        validator=validator.Pattern(
            regex=r"""^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$""", 
        )
    ), 
    field.RestField(
        'ct_blacklist',
        required=False,
        encrypted=False,
        default='^$',
        validator=None
    ), 
    field.RestField(
        'blacklist',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'whitelist',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'sourcetype',
        required=True,
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
        'ct_excluded_events_index',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'max_retries',
        required=False,
        encrypted=False,
        default=3,
        validator=None
    ), 
    field.RestField(
        'recursion_depth',
        required=False,
        encrypted=False,
        default=-1,
        validator=None
    ), 
    field.RestField(
        'max_items',
        required=False,
        encrypted=False,
        default=100000,
        validator=None
    ), 
    field.RestField(
        'character_set',
        required=False,
        encrypted=False,
        default='auto',
        validator=None
    ), 
    field.RestField(
        'is_secure',
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
    'aws_s3',
    model,
)


if __name__ == '__main__':
    logging.getLogger().addHandler(logging.NullHandler())
    admin_external.handle(
        endpoint,
        handler=AdminExternalHandler,
    )
