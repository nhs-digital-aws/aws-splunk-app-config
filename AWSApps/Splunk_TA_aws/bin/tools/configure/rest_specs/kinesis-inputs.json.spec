{
  "name": "kinesis",
  "endpoint": "splunk_ta_aws_aws_kinesis",
  "stanza_fields": [
    {
      "name": "name",
      "required": true,
      "description": "Name"
    },
    {
      "name": "account",
      "required": true,
      "description": "AWS Account"
    },
    {
      "name": "aws_iam_role",
      "required": false,
      "description": "Assume Role"
    },
    {
      "name": "region",
      "required": true,
      "description": "AWS Region"
    },
    {
      "name": "stream_names",
      "required": true,
      "description": "Kinesis Stream Name"
    },
    {
      "name": "init_stream_position",
      "required": true,
      "description": "Initial Stream Position: LATEST or TRIM_HORIZON"
    },
    {
      "name": "encoding",
      "required": false,
      "description": "Encoding with: gzip or (none). (none) means empty string."
    },
    {
      "name": "format",
      "required": false,
      "description": "Record Format: CloudWatchLogs or (none). (none) means empty string."
    },
    {
      "name": "sourcetype",
      "required": true,
      "description": "Sourcetype: aws:kinesis or aws:cloudwatchlogs:vpcflow"
    },
    {
      "name": "index",
      "required": true,
      "description": "Index"
    }
  ]
}
