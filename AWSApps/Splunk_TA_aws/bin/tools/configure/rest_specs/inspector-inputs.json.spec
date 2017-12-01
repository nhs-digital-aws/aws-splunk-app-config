{
  "name": "inspector",
  "endpoint": "splunk_ta_aws_aws_inspector",
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
      "description": "AWS iam role"
    },
    {
      "name": "regions",
      "required": true,
      "description": "AWS Regions"
    },
    {
      "name": "polling_interval",
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
