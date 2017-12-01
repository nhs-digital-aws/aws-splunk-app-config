__author__ = 'frank'

import utils.app_util as util
import time
import json
import recommendation_consts as constants
from base_task import BaseTask
import machine_learning_mod.ml_process_executor as executor
from utils.local_manager import LocalServiceManager
import logging

logger = util.get_logger()
APP = 'saas_app_aws'
APP_NAME = 'splunk_app_aws'


class EC2UsageTask(BaseTask):
    def pre_execute(self):
        # clean staled feedback data
        self.feedback_kao.delete_staled_items(constants.FEEDBACK_EXPIRED_TIME)
        return

    def execute(self):
        latest_time = int(time.time())
        earliest_time = latest_time - constants.CLOUDWATCH_TIME_RANGE

        # get cloudwatch kpis
        spl_results = self.get_cloudwatch_kpis('CPUUtilization', 'NetworkIn', 'NetworkOut', 'DiskWriteBytes', 'DiskReadBytes', earliest_time = earliest_time, latest_time = latest_time)
        cloudwatch_kpi_list = []
        for spl_result in spl_results:
            cloudwatch_kpi_list.append(self._formatSplResult(spl_result))

        # get feedback data
        feedback_list = json.loads(self.read_feebacks(ml_dimension=constants.EC2_DYNAMIC_UP_DOWN))

        # get former recommendation results
        recommendation_result_list = json.loads(self.recommendation_kao.query_items({'ml_dimension': constants.EC2_DYNAMIC_UP_DOWN}))

        # get conf
        conf = self.read_conf()
        # execute ml process
        json_arg = {'cloudwatch': cloudwatch_kpi_list, 'feedback': feedback_list, 'recommendation_results': recommendation_result_list, constants.CONF: conf}

        try:
            output_list = executor.execute_ml_process('upgrade_downgrade_prediction.py', json_arg)
        except Exception as ex:
            error_logger = util.get_logger(logging.ERROR)
            error_logger.error(ex)
            return ex

        # delete former recommendation results of EC2 Upgrade/Downgrade
        self.recommendation_kao.delete_items_by_condition({'ml_dimension': constants.EC2_DYNAMIC_UP_DOWN})

        # insert recommendation results
        if len(output_list) > 0:
            self.recommendation_kao.batch_insert_items(output_list)

        output_message = 'Insert %d ec2 usage recommendations into kvstore.' % len(output_list)
        logger.info(output_message)

        return output_message

    def read_conf(self):
        service = LocalServiceManager(app=APP_NAME, session_key=self.session_key).get_local_service()
        macros_conf = service.confs[constants.CONF_FILE_NAME]
        conf = {}
        if constants.CONF_SANTA in macros_conf:
            content = macros_conf[constants.CONF_SANTA].content
            for field in constants.CONF_FIELD:
                conf[field] = content[field]
        return conf

    def _formatSplResult(self, spl_result):
        resource_id = str(spl_result.get('resource_id'))
        metric_name = str(spl_result.get('metric_name'))
        avg_value = float(str(spl_result.get('avg_value')))
        max_value = float(str(spl_result.get('max_value')))
        timestamp = int(str(spl_result.get('timestamp')))
        count = int(str(spl_result.get('count')))

        result = {'resource_id': resource_id, 'metric_name': metric_name, 'timestamp': timestamp, 'count': count}
        result[metric_name + '_avg_value'] = avg_value
        result[metric_name + '_max_value'] = max_value

        return result