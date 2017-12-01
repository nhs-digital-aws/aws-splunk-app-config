__author__ = 'frank'

import utils.app_util as util
import time
import splunk.search as search
from base_task import BaseTask
import recommendation_consts as constants

logger = util.get_logger()

SPL = '''
    search index=aws_topology_daily_snapshot OR index=aws_topology_history earliest=-1d resourceType="AWS::EC2::SecurityGroup" resourceName!="default"
    | dedup resourceId
    | where resourceStatus!="ResourceDeleted"
    | search NOT (relationships=*i-*)
    | table resourceId
'''

class UnusedSecurityGroupTask(BaseTask):

    def pre_execute(self):
        # delete former recommendation results of Unused security groups
        self.recommendation_kao.delete_items_by_condition({'ml_dimension': constants.UNUSED_SG_DIMENSION})
        return

    def execute(self):
        results = search.searchAll(SPL, sessionKey = self.session_key)

        recommendations = []
        for result in results:
            temp_arr = str(result).split('=')
            if len(temp_arr) == 2 and temp_arr[0] == 'resourceId':
                recommendations.append({
                    'resource_id': temp_arr[1],
                    'resource_type': 'sg',
                    'ml_dimension': constants.UNUSED_SG_DIMENSION,
                    'ml_action': constants.DELETE_ACTION,
                    'ml_priority': 1,
                    'feature': [],
                    'timestamp': int(time.time())
                })

        if len(recommendations) > 0:
            self.recommendation_kao.batch_insert_items(recommendations)

        output_message = 'Insert %d unused security groups into kvstore.' % len(recommendations)
        logger.info(output_message)

        return output_message