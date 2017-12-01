__author__ = 'pezhang'

import json
import sys, os

sys.path.insert(0, os.path.join(os.environ['SPLUNK_HOME'], 'etc', 'apps', 'splunk_app_aws', 'bin'))
import time
import ml_utils
import pandas as pds
import tempfile
import traceback
import AdaBoostRegression
import input_preparation
import recommendation_task.recommendation_consts as const

logger = ml_utils.get_logger()


def recommend_based_on_scores(predictions, accepted_resource_list, conf):
    predictions = predictions.sort(const.RECOMMENDATION_SCORE, ascending=False)
    upgrade_threshold = input_preparation.parse_str_value(conf[const.CONF_UPGRADE_SCORE_FIELD_NAME],
                                                          const.UPGRADE_SCORE, 0, 100)
    downgrade_threshold = input_preparation.parse_str_value(conf[const.CONF_DOWNGRADE_SCORE_FIELD_NAME],
                                                            const.DOWNGRADE_SCORE, 0, 100)
    max_percent = input_preparation.parse_str_value(conf[const.CONF_MAX_PERCENT_FIELD_NAME], const.MAX_PERCENT, 0, 1)

    if len(predictions[predictions[const.RECOMMENDATION_SCORE] > 0]) > 0:
        upgrade_percent_index = int(len(predictions[predictions[const.RECOMMENDATION_SCORE] > 0]) * max_percent)
        upgrade_threshold = max(upgrade_threshold, predictions[const.RECOMMENDATION_SCORE][upgrade_percent_index])

    if len(predictions[predictions[const.RECOMMENDATION_SCORE] < 0]) > 0:
        downgrade_percent_index = len(predictions) - 1 - int(
            len(predictions[predictions[const.RECOMMENDATION_SCORE] < 0]) * max_percent)
        downgrade_threshold = min(downgrade_threshold, predictions[const.RECOMMENDATION_SCORE][downgrade_percent_index])

    result = []
    recommendations = predictions[
        (predictions[const.RECOMMENDATION_SCORE] >= upgrade_threshold) | (
            predictions[const.RECOMMENDATION_SCORE] <= downgrade_threshold)].values
    for rec in recommendations:
        action = const.UPGRADE_ACTION if rec[1] > 0 else const.DOWNGRADE_ACTION

        if (len(accepted_resource_list) == 0) or (rec[0] not in accepted_resource_list):
            logger.info('Recommendation result for instance (%s): score=%f,features=%s'
                        % (rec[0], abs(rec[1]), json.dumps(rec[2])))
            result.append({
                const.INPUT_INSTANCE: rec[0],
                'resource_type': 'i',
                'ml_dimension': const.EC2_DYNAMIC_UP_DOWN,
                const.RECOMMENDATION_ACTION: action,
                const.RECOMMENDATION_SCORE: abs(rec[1]),
                const.INPUT_TIME: int(time.time()),
                const.INPUT_FEATURE: rec[2]
            })
    return result


def predict():
    model = input_preparation.load_model()
    if model is None:
        return json.dumps([])

    helper = AdaBoostRegression.AdaBoostRegression(model)

    json_arg = read_args()
    cloudwatch_list = []
    feedback_list = []
    pre_recommend_list = []
    conf = []
    if const.INPUT_CLOUDWATCH in json_arg:
        cloudwatch_list = input_preparation.format_cloudwatch_list(json_arg[const.INPUT_CLOUDWATCH])

    if const.INPUT_FEEDBACK in json_arg:
        feedback_list = input_preparation.format_json_list(json_arg[const.INPUT_FEEDBACK], const.FEEDBACK_METRICS_NAMES)

    if const.INPUT_RECOMMENDATION in json_arg:
        pre_recommend_list = input_preparation.format_json_list(json_arg[const.INPUT_RECOMMENDATION],
                                                                const.RECOMMENDATION_METRICS_NAMES)

    if const.CONF in json_arg:
        conf = json_arg[const.CONF]

    if (not feedback_list is None) and len(feedback_list) != 0:
        try:
            x, y = input_preparation.update_dataset(feedback_list, pre_recommend_list)
            logger.info('Before updating model: estimator_size=%d' % model.n_estimators)
            logger.info('Before updating model: y=%s' % json.dumps(y.tolist()))
            logger.info('Before updating model: predict_value=%s' % json.dumps(model.predict(x).tolist()))
            helper.update(x, y)
            logger.info('After updating model: estimator_size=%d' % model.n_estimators)
            logger.info('After updating model: predict_value=%s' % json.dumps(model.predict(x).tolist()))
            input_preparation.save_model(model)
        except:
            stack = traceback.format_exc()
            logger.info(str(stack))

    if cloudwatch_list is None or len(cloudwatch_list) == 0:
        return json.dumps([])

    instances = []
    features = []
    try:
        minimum_sample_days = input_preparation.parse_str_value(conf[const.CONF_MINIMUM_SAMPLE_DAYS],
                                                                const.MINIMUM_SAMPLE_DAYS,
                                                                0, 7)
        instances, features = input_preparation.cloudwatch_clean(cloudwatch_list, minimum_sample_days)
    except:
        stack = traceback.format_exc()
        logger.info(str(stack))
        return json.dumps([])

    if len(instances) == 0:
        return json.dumps([])
    scores = model.predict(features)
    predictions = {
        const.INPUT_INSTANCE: instances,
        const.RECOMMENDATION_SCORE: scores,
        const.INPUT_FEATURE: features}
    predictions = pds.DataFrame(predictions,
                                columns=[const.INPUT_INSTANCE, const.RECOMMENDATION_SCORE, const.INPUT_FEATURE])
    # get accepted resources from feedbacks
    accepted_resource_list = input_preparation.get_accepted_resources(json_arg[const.INPUT_FEEDBACK])
    recommendation = recommend_based_on_scores(predictions, accepted_resource_list, conf)

    return json.dumps(recommendation)


# read content from argument file
def read_args():
    process_py_name = sys.argv[1]
    arg_file_path = os.path.join(tempfile.gettempdir(), process_py_name + '.arguments')
    try:
        with open(arg_file_path, 'r') as arg_file:
            arg_content = arg_file.read()
            # parse argument
            json_arg = json.loads(arg_content)
            return json_arg
    except:
        return {}


if __name__ == '__main__':
    print predict()
