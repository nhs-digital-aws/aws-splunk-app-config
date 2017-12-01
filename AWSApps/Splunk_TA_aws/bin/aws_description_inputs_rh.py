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
        'account',
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
        'regions',
        required=True,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'apis',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'sourcetype',
        required=False,
        encrypted=False,
        default='aws:description',
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
    'aws_description_tasks',
    model,
    config_name='aws_description'
)


if __name__ == '__main__':
    logging.getLogger().addHandler(logging.NullHandler())
    admin_external.handle(
        endpoint,
        handler=AdminExternalHandler,
    )
