[aws_cloudtrail://<name>]
aws_account = AWS account used to connect to AWS
aws_region = AWS region of log notification SQS queue
sqs_queue = log notification SQS queue
exclude_describe_events = boolean indicating whether to exclude read-only events from indexing. defaults to true
remove_files_when_done = boolean indicating whether to remove s3 files after reading defaults to false
blacklist = override regex for the "exclude_describe_events" setting. default regex applied is ^(?:Describe|List|Get)
excluded_events_index = name of index to put excluded events into. default is empty, which discards the events

[aws_cloudwatch://<name>]
aws_account = AWS account used to connect to AWS
aws_region = AWS region of CloudWatch metrics
metric_namespace = CloudWatch metric namespace
metric_names = CloudWatch metric names
metric_dimensions = CloudWatch metric dimensions
statistics = CloudWatch metric statistics being requested
period = CloudWatch metric granularity
polling_interval = Polling interval for statistics
aws_iam_role = AWS IAM role that to be assumed.

[aws_s3://<name>]
is_secure = whether use secure connection to AWS
host_name = the host name of the S3 service
aws_account = AWS account used to connect to AWS
bucket_name = S3 bucket
polling_interval = Polling interval for statistics
key_name = S3 key prefix
recursion_depth = For folder keys, -1 == unconstrained
initial_scan_datetime = Splunk relative time
terminal_scan_datetime = Only S3 keys which have been modified before this datetime will be considered. Using datetime format: %Y-%m-%dT%H:%M:%S%z (for example, 2011-07-06T21:54:23-0700).
max_items = Max trackable items.
max_retries = Max number of retry attempts to stream incomplete items.
whitelist = Override regex for blacklist when using a folder key.
blacklist = Keys to ignore when using a folder key.
character_set = The encoding used in your S3 files. Default to 'auto' meaning that file encoding will be detected automatically amoung UTF-8, UTF8 without BOM, UTF-16BE, UTF-16LE, UTF32BE and UTF32LE. Notice that once one specified encoding is set, data input will only handle that encoding.
ct_blacklist = The blacklist to exclude cloudtrail events. Only valid when manually set sourcetype=aws:cloudtrail.
ct_excluded_events_index = name of index to put excluded events into. default is empty, which discards the events
aws_iam_role = AWS IAM role that to be assumed.

[aws_billing://<name>]
aws_account = AWS account used to connect to fetch the billing report
host_name = the host name of the S3 service
bucket_name = S3 bucket
report_file_match_reg = CSV report file in regex, it will override below report type options instead
monthly_report_type = report type for monthly report. options: None, Monthly report, Monthly cost allocation report
detail_report_type = report type for detail report. options: None, Detailed billing report, Detailed billing report with resources and tags
aws_iam_role = AWS IAM role that to be assumed.
temp_folder = Temp folder used for downloading detailed billing csv.zip files.

# below items are internally used only
recursion_depth = recursion depth when iterate files
initial_scan_datetime = start scan time
monthly_timestamp_select_column_list = fields of timestamp extracted from monthly report, seperated by '|'
detail_timestamp_select_column_list = fields of timestamp extracted from detail report, seperated by '|'
time_format_list = time format extraction from existing. e.g. "%Y-%m-%d %H:%M:%S" seperated by '|'
max_file_size_csv_in_bytes = max file size in csv file format, default: 50MB
max_file_size_csv_zip_in_bytes = max file size in csv zip format, default: 1GB
header_look_up_max_lines = maximum lines to look up header of billing report
header_magic_regex = regex of header to look up
monthly_real_timestamp_extraction = for monthly report, regex to extract real timestamp in the montlh report, must contains "(%TIME_FORMAT_REGEX%)", which will be replaced with one value defined in "monthly_real_timestamp_format_reg_list"
monthly_real_timestamp_format_reg_list = for monthly report, regex to match the format of real time string. seperated by '|'

[aws_config://<name>]
aws_account = AWS account used to connect to AWS
aws_region = AWS region of log notification SQS queue
sqs_queue = Starling Notification SQS queue
enable_additional_notifications = deprecated
polling_interval = Polling interval for statistics

[aws_description://<name>]
placeholder = placeholder. Please see aws_description_tasks.conf.spec for task spec.

[aws_cloudwatch_logs://<name>]
placeholder = placeholder. Please see aws_cloudwatch_logs_tasks.conf.spec for task spec.

[aws_config_rule://<name>]
placeholder = placeholder

[aws_inspector://<name>]
placeholder = placeholder

[aws_kinesis://<name>]
placeholder = placeholder

[splunk_ta_aws_sqs://<name>]
placeholder = placeholder

[splunk_ta_aws_logs://<name>]
log_type =
aws_account =
host_name =
bucket_name =
bucket_region =
log_file_prefix =
log_start_date =
log_name_format =
aws_iam_role = AWS IAM role that to be assumed.
max_retries = @integer:[-1, 1000]. default is -1. -1 means retry until success.
max_fails = @integer: [0, 10000]. default is 10000. Stop discovering new keys if the number of failed files exceeded the max_fails.
max_number_of_process = @integer:[1, 64]. default is 2.
max_number_of_thread = @integer:[1, 64]. default is 4.

[aws_sqs_based_s3://<name>]
aws_account = The AWS account or EC2 IAM role the input uses to access SQS messages and S3 keys.
aws_iam_role = AWS IAM role that to be assumed in the input.
sqs_queue_url = Name of SQS queue to which notifications of S3 file(s) creation are sent.
sqs_queue_region = Name of the AWS region in which the notification queue is located.
sqs_batch_size = @integer:[1, 10]. Max number of messages to pull from SQS in one batch. Default is 10.
s3_file_decoder = Name of a decoder which decodes files into events: CloudTrail, Config, S3 Access Logs, ELB Access Logs, CloudFront Access Logs, and CustomLogs.
use_raw_hec = scheme://netloc/token, for instance, https://192.168.1.1:8088/550E8400-E29B-41D4-A716-446655440000.
