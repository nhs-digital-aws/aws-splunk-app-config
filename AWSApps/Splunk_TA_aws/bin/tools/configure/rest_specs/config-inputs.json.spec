{
    "name": "config",
    "endpoint": "aws_config_inputs_rh_ucc",
    "stanza_fields": [
        {
          "name": "name",
          "required": true,
          "description": "Name"
        },
        {
            "description": "AWS Account",
            "name": "aws_account",
            "required": true
        },
        {
            "description": "AWS Region",
            "name": "aws_region",
            "required": true
        },
        {
            "description": "SQS Queue Name",
            "name": "sqs_queue",
            "required": true
        },
        {
            "description": "Interval",
            "name": "polling_interval",
            "required": true
        },
        {
            "name": "sourcetype",
            "required": true,
            "description": "aws:config"
        },
        {
            "description": "Index",
            "name": "index",
            "required": true
        },
        {
            "description": "enable_additional_notifications",
            "name": "enable_additional_notifications",
            "required": false
        }
    ]
}
