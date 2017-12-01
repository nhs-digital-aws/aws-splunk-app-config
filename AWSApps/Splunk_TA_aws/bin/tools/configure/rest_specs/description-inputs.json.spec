{
  "name": "description",
  "endpoint": "splunk_ta_aws_aws_description",
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
      "name": "regions",
      "required": true,
      "description": "AWS Regions"
    },
    {
      "name": "apis",
      "required": true,
      "description": "APIs: ec2_volumes/3600,ec2_instances/3600,ec2_reserved_instances/3600,ebs_snapshots/3600,classic_load_balancers/3600,application_load_balancers/3600,vpcs/3600,vpc_network_acls/3600,cloudfront_distributions/3600,vpc_subnets/3600,rds_instances/3600,ec2_key_pairs/3600,ec2_security_groups/3600,ec2_images/3600,ec2_addresses/3600,lambda_functions/3600,s3_buckets/3600"
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
