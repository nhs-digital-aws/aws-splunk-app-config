[<name>]
account = AWS account used to connect to AWS
regions = AWS regions to get data from, splitted by ','
apis = APIs you want to collect data with, and intervals for each api, in the format of <api name>/<api interval seconds>[,<api name>/<api interval seconds>...] See docs for details.
aws_iam_role = AWS IAM role that to be assumed.
sourcetype = The sourcetype you want.
index = The index you want to put data in.