{
  "name": "account",
  "endpoint": "splunk_ta_aws_aws_account",
  "stanza_fields": [
    {
      "name": "name",
      "required": true,
      "description": "Name"
    },
    {
      "name": "key_id",
      "required": true,
      "description": "Key ID"
    },
    {
      "name": "secret_key",
      "required": true,
      "description": "Secrete Key"
    },
    {
      "name": "category",
      "required": true,
      "description": "Region Category"
    },
    {
      "name": "iam",
      "required": false,
      "description": "Is EC2 Instance Role"
    }
  ]
}
