{
  "name": "incr-s3",
  "endpoint": "splunk_ta_aws_splunk_ta_aws_logs",
  "stanza_fields": [
    {
      "name": "name",
      "required": true,
      "description": "Name"
    },
    {
      "name": "aws_account",
      "required": true,
      "description": "AWS Account"
    },
    {
      "name": "aws_iam_role",
      "required": false,
      "description": "Assume Role"
    },
    {
      "name": "host_name",
      "required": true,
      "description": "S3 Host Name"
    },
    {
      "name": "bucket_name",
      "required": true,
      "description": "S3 Bucket"
    },
    {
      "name": "log_type",
      "required": true,
      "description": "Log Type: cloudtrail, s3:accesslogs, cloudfront:accesslogs and elb:accesslogs"
    },
    {
      "name": "log_file_prefix",
      "required": false,
      "description": "Log File Prefix"
    },
    {
      "name": "log_start_date",
      "required": false,
      "description": "Log Start Date"
    },
    {
      "name": "log_name_format",
      "required": false,
      "description": "Distribution ID (Required for log_type='cloudfront:accesslogs')"
    },
    {
      "name": "interval",
      "required": true,
      "description": "Interval"
    },
    {
      "name": "sourcetype",
      "required": true,
      "description": "Sourcetype"
    },
    {
      "name": "index",
      "required": true,
      "description": "Index"
    }
  ]
}
