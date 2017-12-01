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
        'monthly_report_type',
        required=False,
        encrypted=False,
        default='Monthly cost allocation report',
        validator=None
    ), 
    field.RestField(
        'detail_report_type',
        required=False,
        encrypted=False,
        default='Detailed billing report with resources and tags',
        validator=None
    ), 
    field.RestField(
        'report_file_match_reg',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'temp_folder',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'recursion_depth',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'monthly_timestamp_select_column_list',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'detail_timestamp_select_column_list',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'time_format_list',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'max_file_size_csv_in_bytes',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'max_file_size_csv_zip_in_bytes',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'header_look_up_max_lines',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'header_magic_regex',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'monthly_real_timestamp_extraction',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'monthly_real_timestamp_format_reg_list',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'interval',
        required=False,
        encrypted=False,
        default=86400,
        validator=validator.Number(
            max_val=31536000, 
            min_val=0, 
        )
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
        'sourcetype',
        required=False,
        encrypted=False,
        default='aws:billing',
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
    'aws_billing',
    model,
)


if __name__ == '__main__':
    logging.getLogger().addHandler(logging.NullHandler())
    admin_external.handle(
        endpoint,
        handler=AdminExternalHandler,
    )
