import aws_bootstrap_env
from splunktaucclib.rest_handler.endpoint import (
    field,
    validator,
    RestModel,
    SingleModel,
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
        'aws_region',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'sqs_queues',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'interval',
        required=True,
        encrypted=False,
        default=30,
        validator=validator.Number(
            max_val=31536000, 
            min_val=0, 
        )
    ), 
    field.RestField(
        'sourcetype',
        required=True,
        encrypted=False,
        default='aws:sqs',
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


endpoint = SingleModel(
    'aws_sqs_tasks',
    model,
    config_name='splunk_ta_aws_sqs'
)


if __name__ == '__main__':
    logging.getLogger().addHandler(logging.NullHandler())
    admin_external.handle(
        endpoint,
        handler=AdminExternalHandler,
    )
