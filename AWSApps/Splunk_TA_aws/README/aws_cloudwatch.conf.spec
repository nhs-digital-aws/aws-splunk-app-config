[logging]
log_level = DEBUG, INFO or ERROR

[global_settings]
use_hec = 0 or 1, use Http Event collector to inject data
hec_port = 8088, Http Event Collector port
use_kv_store = 0 or 1, use KVStore to do ckpt
use_multiprocess = 0 or 1, use use_multiprocess to do data collection
max_api_saver_time = 7200, Maximum sleep time when there is no CloudWatch data for that dimension and metric name. For example, the AddOn polls CloudWatch metrics for an EC2 stopped instance, when it detects there are 3 times there is no CloudWatch data, it will try to sleep for a period of time (max_api_saver_time) and then retri again, this can save lots of API calls for stopped EC2 instance or other service
