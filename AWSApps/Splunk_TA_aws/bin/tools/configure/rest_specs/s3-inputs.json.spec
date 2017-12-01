{
  "name": "s3",
  "endpoint": "splunk_ta_aws_aws_s3",
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
      "name": "key_name",
      "required": false,
      "description": "S3 Key Prefix"
    },
    {
      "name": "initial_scan_datetime",
      "required": false,
      "description": "Start Date/Time"
    },
    {
      "name": "blacklist",
      "required": false,
      "description": "Blacklist"
    },
    {
      "name": "whitelist",
      "required": false,
      "description": "Whitelist"
    },
    {
      "name": "polling_interval",
      "required": true,
      "description": "Interval"
    },
    {
      "name": "sourcetype",
      "required": true,
      "description": "Sourcetype: aws:cloudtrail, aws:s3:accesslogs, aws:cloudfront:accesslogs and aws:elb:accesslogs"
    },
    {
      "name": "index",
      "required": true,
      "description": "Index"
    }
  ]
}
