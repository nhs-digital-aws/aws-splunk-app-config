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
        'metric_namespace',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'metric_names',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'metric_dimensions',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'statistics',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'polling_interval',
        required=False,
        encrypted=False,
        default='3600',
        validator=validator.Number(
            max_val=86400, 
            min_val=60, 
        )
    ), 
    field.RestField(
        'period',
        required=False,
        encrypted=False,
        default='300',
        validator=validator.Number(
            max_val=86400, 
            min_val=60, 
        )
    ), 
    field.RestField(
        'sourcetype',
        required=False,
        encrypted=False,
        default='aws:cloudwatch',
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
    'aws_cloudwatch',
    model,
)


if __name__ == '__main__':
    logging.getLogger().addHandler(logging.NullHandler())
    admin_external.handle(
        endpoint,
        handler=AdminExternalHandler,
    )
