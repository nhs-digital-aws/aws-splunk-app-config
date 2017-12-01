KVSTORE_TO_CONF_SPL = {
    'cloudtrail': {
        'h':
            '`aws-cloudtrail((aws_account_id="{0}"), (region="*"))` eventName="{1}" | eval response=if(errorCode=="success","success", "error")' +
            '| lookup unauthorized_errorCode errorCode OUTPUT Unauthorized | eval response=if(Unauthorized=="true", "unauthorized", response)' +
            '| search response="{3}" | timechart span=1h count as {2} | fillnull',
        'd':
            '| savedsearch "CloudTrail Timechart Search" | search aws_account_id="{0}" eventName="{1}" response="{3}"' +
            '| timechart span=1d sum(count) as {2} | fillnull'
    },
    'billing': {
        'd':
            '`aws-cloudwatch-billing((LinkedAccountId="{0}"), "*")` | `aws-cloudwatch-dimension-rex("ServiceName", "service")` ' +
            '| search service="{1}" | stats sum(Sum) as sum by _time, service' +
            '| eval day=strftime(_time, "%Y/%m/%d") | dedup day service sortby -_time |  timechart span=1d sum(sum) as {2} | preprocessbilling'
    }
}
DATA_MIGRATE_SPL = '''
    search index="aws_anomaly_detection" ruleName="{0}" granularity="{1}" outlier!="N/A" | regex parameters="{2}"
    | eval job_id="{3}", value_{4}=outlier, outlier_{4}="True",
    abnormal_rate_len=len(abnormalRate), abnormal_rate=tonumber(substr(abnormalRate, 0, abnormal_rate_len-1)),
    severity_{4}=case(abnormal_rate > 500, "4", abnormal_rate > 250, "3", abnormal_rate > 100, "2", abnormal_rate > 0, "1", true(), "0")
    | dedup _time, value_{4} | table _time, job_id, value_{4}, outlier_{4}, severity_{4}
    | collect index="{5}" sourcetype="{6}"
'''

KVSTORE_NAMESPACE = 'anomalyDetectionSettings_kvstore'
DEFAULT_PRIORIY = 1
DEFAULT_MODE = 3
JOB_NAME = 'job_name'
JOB_SEARCH = 'job_search'
