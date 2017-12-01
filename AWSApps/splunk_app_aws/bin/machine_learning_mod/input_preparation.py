__author__ = 'pezhang'

import os
import pickle
import time
import numpy as np
import json
import pandas as pds
import recommendation_task.recommendation_consts as const
import ml_utils
logger = ml_utils.get_logger()

MODEL_PATH = os.path.join(const.APP_BIN_PATH, 'machine_learning_mod', 'model')
CLOUDWATCH_CNT_NAME = ['CPUUtilization_count', 'NetworkIn_count', 'NetworkOut_count', 'DiskReadBytes_count',
                       'DiskWriteBytes_count']
CLOUDWATCH_METRICS = 'metric_name'
CLOUDWATCH_COUNT = 'count'
DAY_SECONDS = 86400
METRIC_CNT = 5
CNT_THRESHOLD = 1. / 24


def save_model(model):
    with open(MODEL_PATH, 'w') as file:
        pickle.dump(model, file)



def load_model():
    try:
        with open(MODEL_PATH, 'r') as file:
            return pickle.load(file)
    except:
        return None

# parse str value
def parse_str_value(str, default_value, min_value, max_value):
    try:
        return min(max(float(str), min_value), max_value)
    except:
        return default_value

# get accepted feedbacks of current dimension
def get_accepted_resources(feedback_list):
    accepted_resource_list = []
    last_day_timestamp = int(time.time()) / DAY_SECONDS * DAY_SECONDS

    for feedback_data in feedback_list:
        # 1. feedback is 'action'; 2. dimension is EC2 upgrade/downgrade; 3. time is last day
        if feedback_data['feedback'] == 'action' and feedback_data['ml_dimension'] == const.EC2_DYNAMIC_UP_DOWN and \
                        feedback_data['timestamp'] >= last_day_timestamp:
            accepted_resource_list.append(feedback_data['resource_id'])
    logger.info('Instances (%s) has just been accepted and will not be recommended later.' %(json.dumps(accepted_resource_list)))
    return accepted_resource_list


# transform cloudwatch list format, to fit machine learning algorithm
def format_cloudwatch_list(cloudwatch_list):
    instance_cloudwatch_map = {}
    # for i in range(len(cloudwatch_list)):
    # cloudwatch_data = cloudwatch_list.loc[i]
    for cloudwatch_data in cloudwatch_list:
        resource_id = cloudwatch_data[const.INPUT_INSTANCE]
        time = cloudwatch_data[const.INPUT_TIME]
        key = '%s#%d' % (resource_id, time)

        if key not in instance_cloudwatch_map.keys():
            instance_cloudwatch_map[key] = {}

        metric_name = cloudwatch_data[CLOUDWATCH_METRICS]
        avg_value_name = metric_name + '_avg_value'
        max_value_name = metric_name + '_max_value'
        metric_count_name = metric_name + '_count'
        instance_cloudwatch_map[key][avg_value_name] = cloudwatch_data[avg_value_name]
        instance_cloudwatch_map[key][max_value_name] = cloudwatch_data[max_value_name]
        instance_cloudwatch_map[key][metric_count_name] = cloudwatch_data[CLOUDWATCH_COUNT]

    formatted_cloudwatch_list = []
    for key in instance_cloudwatch_map:
        (resource_id, time) = key.split('#')
        cloudwatch_array = [resource_id]
        for feature_name in const.CLOUDWATCH_METRICS_NAMES:
            if feature_name in instance_cloudwatch_map[key]:
                cloudwatch_array.append(instance_cloudwatch_map[key][feature_name])
            else:
                cloudwatch_array.append(0)
        cloudwatch_array.append(int(time))
        formatted_cloudwatch_list.append(cloudwatch_array)

    return formatted_cloudwatch_list


# transform json list format, to fit machine learning algorithm
def format_json_list(list, metric_names):
    formatted_list = []
    for data in list:
        array = []
        for metric_name in metric_names:
            if metric_name in data:
                array.append(data[metric_name])
            else:
                if metric_name == const.INPUT_FEATURE:
                    array.append([np.nan])
                else:
                    array.append(np.nan)
        formatted_list.append(array)
    return formatted_list


def cloudwatch_clean(cloudwatch, minimum_sample_days):
    column_names = const.CLOUDWATCH_METRICS_NAMES[:]
    column_names.append(const.INPUT_TIME)
    column_names.insert(0, const.INPUT_INSTANCE)
    cloudwatch = pds.DataFrame(cloudwatch, columns=column_names)

    cloudwatch = cloudwatch.sort([const.INPUT_TIME], ascending=False)
    max_time = cloudwatch[const.INPUT_TIME].max() / DAY_SECONDS
    cnt_threshold = 0
    if len(cloudwatch) != 0:
        cnt_threshold = int(cloudwatch[CLOUDWATCH_CNT_NAME].values.max() * CNT_THRESHOLD)

    instances = cloudwatch[const.INPUT_INSTANCE].drop_duplicates()
    valid_instances = []
    features = []
    for ins in instances:
        cur_ins_feature = cloudwatch[cloudwatch[const.INPUT_INSTANCE] == ins][const.CLOUDWATCH_METRICS_NAMES]
        feature_indexes = max_time - cloudwatch[cloudwatch[const.INPUT_INSTANCE] == ins][
                                         const.INPUT_TIME].values / DAY_SECONDS

        if len(feature_indexes) == 0:
            continue

        result = range(METRIC_CNT * 2 * const.CLOUDWATCH_DAYS)
        no_enough = False  # not enough to construct a vaild feature row
        for i in xrange(METRIC_CNT):
            max_values = cur_ins_feature[const.CLOUDWATCH_METRICS_NAMES[i * 3]].values
            avg_values = cur_ins_feature[const.CLOUDWATCH_METRICS_NAMES[i * 3 + 1]].values
            metric_cnt = cur_ins_feature[const.CLOUDWATCH_METRICS_NAMES[i * 3 + 2]].values
            no_enough_index = np.where(metric_cnt < cnt_threshold)[0]
            if len(max_values) - len(no_enough_index) <= minimum_sample_days:
                no_enough = True
                break
            else:
                result[i * const.CLOUDWATCH_DAYS:(i + 1) * const.CLOUDWATCH_DAYS] = [np.max(
                    max_values)] * const.CLOUDWATCH_DAYS
                result[(i + 1) * const.CLOUDWATCH_DAYS:(i + 2) * const.CLOUDWATCH_DAYS] = [np.mean(
                    avg_values)] * const.CLOUDWATCH_DAYS
                start_index = 0
                for j in xrange(len(feature_indexes)):
                    if start_index >= len(no_enough_index) or j != no_enough_index[start_index]:
                        result[i * const.CLOUDWATCH_DAYS + feature_indexes[j]] = max_values[j]
                        result[(i + 1) * const.CLOUDWATCH_DAYS + feature_indexes[j]] = avg_values[j]
                    else:
                        start_index += 1

        if not no_enough:
            features.append(result)
            valid_instances.append(ins)

    logger.info("Clean cloudwatch data: initial_instances_set_len=%d,valid_instances_set_len=%d." % (len(instances), len(valid_instances)))
    return valid_instances, features

# dedup feedback based on resource_id (instance_id) and timestamp
def dedup_feedback(feedback):
    feedback = feedback.sort(columns=[const.INPUT_TIME], ascending=[1]) # sort feedback in ascending timestamp
    deleted_row = []
    instances_id_set = set([])
    for i in xrange(len(feedback)):
        instance_id = feedback.loc[i, const.INPUT_INSTANCE]
        if instance_id in instances_id_set:
            deleted_row.append(i)
        else:
            instances_id_set.add(instance_id)
    return feedback.drop(feedback.index[deleted_row]).reset_index(drop=True)

# use feedback and yesterday's recommendation results to form updated dataset
def update_dataset(feedback, recommendation):
    feedback = pds.DataFrame(feedback, columns=const.FEEDBACK_METRICS_NAMES)
    feedback = dedup_feedback(feedback)
    recommendation = pds.DataFrame(recommendation, columns=const.RECOMMENDATION_METRICS_NAMES)
    recommendation_with_no_feedback = [recommendation[const.RECOMMENDATION_RECOMMENDATION_ID][i] not in
                                       feedback[const.FEEDBACK_RECOMMENDATION_ID].values for i in
                                       xrange(len(recommendation))]
    recommendation = recommendation[recommendation_with_no_feedback]
    for i in xrange(len(feedback)):
        if feedback.loc[i, const.RECOMMENDATION_ACTION] == const.DOWNGRADE_ACTION:
            feedback.loc[i, const.RECOMMENDATION_SCORE] *= -1
        if feedback.loc[i, const.FEEDBACK_ACTION] == const.IGNORE_ACTION:
            feedback.loc[i, const.RECOMMENDATION_SCORE] *= const.IGNORE_COEFFS
        elif feedback.loc[i, const.FEEDBACK_ACTION] == const.READ_ACTION:
            feedback.loc[i, const.RECOMMENDATION_SCORE] *= const.READ_COEFFS
        else:
            feedback.loc[i, const.RECOMMENDATION_SCORE] *= const.ACTION_COEFFS
    x = np.array(feedback[const.INPUT_FEATURE].values.tolist(), dtype=float)
    y = np.array(feedback[const.RECOMMENDATION_SCORE].values.tolist(), dtype=float)

    if len(recommendation) != 0:
        recommendation_y = np.array(recommendation[const.RECOMMENDATION_SCORE].values.tolist(), dtype=float)
        recommendation_x = np.array(recommendation[const.INPUT_FEATURE].values.tolist(), dtype=float)
        nega_index = np.where(recommendation[const.RECOMMENDATION_ACTION] == const.DOWNGRADE_ACTION)[0]
        recommendation_y[nega_index] *= -1
        y = np.append(y, recommendation_y, axis=0)
        x = np.append(x, recommendation_x, axis=0)

    y_index = set(np.where(np.isnan(y))[0].tolist())
    x_index = set([i for i in xrange(len(x)) if np.isnan(x[i]).sum() >= 1])
    index = list(x_index | y_index)
    return np.delete(x, index, axis=0), np.delete(y, index, axis=0)
