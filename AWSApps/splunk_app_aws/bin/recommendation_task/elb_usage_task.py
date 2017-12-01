__author__ = 'frank'

import utils.app_util as util
import time
import splunk.search as search
from base_task import BaseTask
import recommendation_consts as constants

logger = util.get_logger()

SPL = '''
    search %s sourcetype="aws:description" source="*_load_balancers" earliest=-1d
    | eval name=if(isnull(name), LoadBalancerName, name)
    | dedup account_id, region, name
    | eval instances=if(isnotnull('instances{}.state'), mvzip('instances{}.instance_id', 'instances{}.state'),
    mvzip('TargetGroups{}.TargetHealthDescriptions{}.Target.Id','TargetGroups{}.TargetHealthDescriptions{}.TargetHealth.State')),
    healthy_instance_state = mvfilter(match(instances,"\w+,InService$") OR match(instances, "\w+,healthy$")) ,
    healthy_instance_count=if(isnull(healthy_instance_state),0, mvcount(healthy_instance_state))
    | where healthy_instance_count = 0
    | fields name, region, account_id, LoadBalancerArn
    | join region [|inputlookup regions]
    | eval resourceId=if(isnotnull('LoadBalancerArn'), LoadBalancerArn, name+" ("+account_id+", "+location+")")
    | table resourceId
'''

# TODO: May introduce more ELB recommendations, like not-best-practise, not-autoscaling, etc. So name it "ElbUsageTask".
class ElbUsageTask(BaseTask):

    def pre_execute(self):
        # delete former recommendation results of Unused ELBs
        self.recommendation_kao.delete_items_by_condition({'ml_dimension': constants.UNUSED_ELB_DIMENSION})
        return

    def execute(self):
        index_option_value = util.get_option_from_conf(self.session_key, 'macros', 'aws-description-index', 'definition')

        results = search.searchAll(SPL % (index_option_value), sessionKey = self.session_key)

        recommendations = []
        for result in results:
            temp_arr = str(result).split('=')
            if len(temp_arr) == 2 and temp_arr[0] == 'resourceId':
                recommendations.append({
                    'resource_id': temp_arr[1],
                    'resource_type': 'elb',
                    'ml_dimension': constants.UNUSED_ELB_DIMENSION,
                    'ml_action': constants.DELETE_ACTION,
                    'ml_priority': 1,
                    'feature': [],
                    'timestamp': int(time.time())
                })

        if len(recommendations) > 0:
            self.recommendation_kao.batch_insert_items(recommendations)

        output_message = 'Insert %d unused elbs into kvstore.' % len(recommendations)
        logger.info(output_message)

        return output_message