__author__ = 'frank'

import os

# collection names
RECOMMENDATION_COLLECTION = 'recommendationResults_kvstore'
FEEDBACK_COLLECTION = 'recommendationFeedbacks_kvstore'

# user actions
DELETE_ACTION = 'Delete'
READ_ACTION = 'read'
IGNORE_ACTION = 'ignore'
UPGRADE_ACTION = 'Upgrade'
DOWNGRADE_ACTION = 'Downgrade'

# configure related
CONF = 'conf'
CONF_FILE_NAME = 'recommendation'
CONF_SANTA = 'ec2'
CONF_FIELD = ['instance_upgrade_threshold_score', 'instance_downgrade_threshold_score', 'instance_threshold_percent',
              'instance_minimum_sample_days']

# recommendation dimensions
UNUSED_SG_DIMENSION = 'Unused Security Group'
UNUSED_ELB_DIMENSION = 'Unused ELB'
EC2_DYNAMIC_UP_DOWN = 'EC2 Dynamic Up/Downgrade'

# AdaBoostRegression model coeffs
MAX_ESTIMATORS = 100
MAX_ADD_ESTIMATORS = 150
MIN_ESTIMATORS = 10
LEARNING_RATE = 1
TRUST_FEEDBACK_CNT = 3
MIN_ESTIMATOR_PRESERVE_PERCENTAGE = 0.8
MAX_ESTIMATOR_ERROR = 0.45
MIN_ESTIMATOR_ERROR = 0.1
IGNORE_COEFFS = 0.3
READ_COEFFS = 0.6
ACTION_COEFFS = 1.2

# up/downgrade recommendation threshold
UPGRADE_SCORE = 70
DOWNGRADE_SCORE = -70
MAX_PERCENT = 0.1
MINIMUM_SAMPLE_DAYS = 4

# up/downgrade recommendation threshold field name in recommendation conf
CONF_UPGRADE_SCORE_FIELD_NAME = 'instance_upgrade_threshold_score'
CONF_DOWNGRADE_SCORE_FIELD_NAME = 'instance_downgrade_threshold_score'
CONF_MAX_PERCENT_FIELD_NAME = 'instance_threshold_percent'
CONF_MINIMUM_SAMPLE_DAYS = 'instance_minimum_sample_days'

# input clean
CLOUDWATCH_METRICS_NAMES = ['CPUUtilization_max_value','CPUUtilization_avg_value','CPUUtilization_count','NetworkIn_max_value',
                            'NetworkIn_avg_value','NetworkIn_count','NetworkOut_max_value','NetworkOut_avg_value',
                            'NetworkOut_count','DiskReadBytes_max_value','DiskReadBytes_avg_value','DiskReadBytes_count',
                            'DiskWriteBytes_max_value','DiskWriteBytes_avg_value','DiskWriteBytes_count']
FEEDBACK_METRICS_NAMES = ['timestamp','resource_id','recomm_id','ml_action','ml_priority','feature','feedback']
RECOMMENDATION_METRICS_NAMES = ['_key', 'ml_action','ml_priority','feature']
FEEDBACK_ACTION = 'feedback'
RECOMMENDATION_ACTION = 'ml_action'
RECOMMENDATION_SCORE = 'ml_priority'
FEEDBACK_RECOMMENDATION_ID = 'recomm_id'
RECOMMENDATION_RECOMMENDATION_ID = '_key'
CLOUDWATCH_DAYS = 7
DAY_SECONDS = 86400

INPUT_FEATURE = 'feature'
INPUT_INSTANCE = 'resource_id'
INPUT_TIME = 'timestamp'
INPUT_CLOUDWATCH = 'cloudwatch'
INPUT_FEEDBACK = 'feedback'
INPUT_RECOMMENDATION = 'recommendation_results'

# paths
APP_BIN_PATH = os.path.join(os.environ['SPLUNK_HOME'], 'etc', 'apps', 'splunk_app_aws', 'bin')

# expired time
FEEDBACK_EXPIRED_TIME = 1 * 86400

# cloudwatch kpi time range (CLOUDWATCH_DAYS days by default)
CLOUDWATCH_TIME_RANGE = (CLOUDWATCH_DAYS + 1) * 86400

# cloudwatch kpi spl (currently only for EC2)
CLOUDWATCH_SPL = '''
    search {index} sourcetype="aws:cloudwatch" metric_dimensions="InstanceId=[*]" ({metric_name_conditions}) Average=* Maximum=*
    | eval timestamp = strftime(_time, "%s"), timestamp = floor(timestamp/86400)*86400
    | eval len=len(metric_dimensions), resource_id=substr(metric_dimensions, 13, len-13)
    | stats avg(Average) as avg_value, avg(Maximum) as max_value, count by resource_id, metric_name, timestamp
    | table resource_id, avg_value, max_value, metric_name, timestamp, count
    | fillnull
'''