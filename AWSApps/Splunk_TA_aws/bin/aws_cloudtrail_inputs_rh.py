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
        'aws_region',
        required=True,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'sqs_queue',
        required=True,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'remove_files_when_done',
        required=False,
        encrypted=False,
        default=False,
        validator=None
    ), 
    field.RestField(
        'exclude_describe_events',
        required=False,
        encrypted=False,
        default=True,
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
        'excluded_events_index',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'interval',
        required=False,
        encrypted=False,
        default=30,
        validator=validator.Number(
            max_val=31536000, 
            min_val=0, 
        )
    ), 
    field.RestField(
        'sourcetype',
        required=False,
        encrypted=False,
        default='aws:cloudtrail',
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
        'disabled',
        required=False,
        validator=None
    )

]
model = RestModel(fields, name=None)



endpoint = DataInputModel(
    'aws_cloudtrail',
    model,
)


if __name__ == '__main__':
    logging.getLogger().addHandler(logging.NullHandler())
    admin_external.handle(
        endpoint,
        handler=AdminExternalHandler,
    )
