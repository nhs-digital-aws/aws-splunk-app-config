{
  "name": "sqs-based-s3",
  "endpoint": "splunk_ta_aws_aws_sqs_based_s3",
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
      "name": "sqs_queue_region",
      "required": true,
      "description": "Name of the SQS region"
    },
    {
      "name": "sqs_queue_url",
      "required": true,
      "description": "URL of SQS queue"
    },
    {
      "name": "sqs_batch_size",
      "required": true,
      "description": "Max number of messages"
    },
    {
      "name": "s3_file_decoder",
      "required": true,
      "description": "Name of a decoder"
    },
    {
      "name": "interval",
      "required": true,
      "description": "Interval"
    },
    {
      "name": "index",
      "required": true,
      "description": "Index"
    },
    {
      "name": "sourcetype",
      "required": true,
      "description": "sourcetype"
    }
  ]
}
