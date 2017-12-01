[<name>]
account = AWS account used to connect to AWS
region = AWS region of CloudWatch Logs
groups = Log group names to get data from, splitted by ','
delay = Number of seconds, recommended to be 1800. Each time the modular input will query the CloudWatch Logs events no later than <delay> seconds before now. This is to assure your log events have already been ingested by CloudWatch Logs when the modular input queries them.
interval = Number of seconds, recommended to be 600. The modular input will make a query once per interval.
only_after = GMT time string in '%Y-%m-%dT%H:%M:%S' format. If set, only events after <only_after> will be queried and indexed.
stream_matcher = REGEX to strictly match stream names. Default to .*
sourcetype = The sourcetype you want.
index = The index you want to put data in.