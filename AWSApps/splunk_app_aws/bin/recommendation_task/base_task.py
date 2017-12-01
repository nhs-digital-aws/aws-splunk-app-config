__author__ = 'frank'

import time
import splunk.search as search
import recommendation_consts as constants
from dao.kvstore_access_object import KVStoreAccessObject
import utils.app_util as util

logger = util.get_logger()


class BaseTask(object):
    def __init__(self, session_key = None):
        self.session_key = session_key
        self.feedback_kao = KVStoreAccessObject(constants.FEEDBACK_COLLECTION, session_key)
        self.recommendation_kao = KVStoreAccessObject(constants.RECOMMENDATION_COLLECTION, session_key)

    def pre_execute(self):
        """
        Executes before the task of machine learning runs. (optional)
        :return:
        """
        return

    def post_execute(self):
        """
        Executes after the task of machine learning runs. (optional)
        :return:
        """
        return

    def execute(self):
        """
        Executes the task of machine learning.
        Each task class needs to implement this hook.
        :return: output message (string)
        """
        raise NotImplementedError('This method needs to be implemented in each task.')

    def read_feebacks(self, ml_dimension):
        """
        Reads feedbacks from kvstore.
        :param ml_dimension: dimension for machine learning
        :return:
        """
        feebacks = self.feedback_kao.query_items({'ml_dimension': ml_dimension})
        return feebacks

    def get_cloudwatch_kpis(self, *metric_names, **time_params):
        """
        Get Cloudwatch data of some metric.
        :param metric_name: Cloudwatch metric name
        :param time_params: a dict, has "earliest_time" and "latest_time" key
        :return: an array of "splunk.search.Result" object
        """
        index_option_value = util.get_option_from_conf(self.session_key, 'macros', 'aws-cloudwatch-index', 'definition')
        spl = constants.CLOUDWATCH_SPL

        metric_name_list = []
        for metric_name in metric_names:
            metric_name_list.append('metric_name="%s"' % metric_name)

        if time_params is None or 'earliest_time' not in time_params:
            time_params['earliest_time'] = 0

        if time_params is None or 'latest_time' not in time_params:
            time_params['latest_time'] = int(time.time())

        results = search.searchAll(spl.format(index = index_option_value, metric_name_conditions = ' OR '.join(metric_name_list)), sessionKey = self.session_key, earliestTime = time_params['earliest_time'], latestTime = time_params['latest_time'])
        return results