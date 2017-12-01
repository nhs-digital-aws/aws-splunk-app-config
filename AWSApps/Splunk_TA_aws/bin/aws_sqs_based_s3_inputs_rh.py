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
        'sqs_queue_region',
        required=True,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'sqs_queue_url',
        required=True,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'sqs_batch_size',
        required=False,
        encrypted=False,
        default='10',
        validator=validator.Number(
            max_val=10, 
            min_val=1, 
        )
    ), 
    field.RestField(
        's3_file_decoder',
        required=True,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'sourcetype',
        required=True,
        encrypted=False,
        default=None,
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
        'interval',
        required=False,
        encrypted=False,
        default='300',
        validator=validator.Number(
            max_val=31536000, 
            min_val=0, 
        )
    ), 

    field.RestField(
        'disabled',
        required=False,
        validator=None
    )

]
model = RestModel(fields, name=None)



endpoint = DataInputModel(
    'aws_sqs_based_s3',
    model,
)


if __name__ == '__main__':
    logging.getLogger().addHandler(logging.NullHandler())
    admin_external.handle(
        endpoint,
        handler=AdminExternalHandler,
    )
