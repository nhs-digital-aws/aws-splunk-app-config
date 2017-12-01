[<name>]
account = AWS account used to connect to AWS
region = AWS region
stream_names = Kinesis stream names in a comma-separated list. Leave empty to collect all streams.
encoding = gzip or empty
format = CloudWatchLogs or empty
init_stream_position = TRIM_HORIZON or LATEST
aws_iam_role = AWS IAM role that to be assumed.
sourcetype = Sourcetype
index = The index you want to put data in.
