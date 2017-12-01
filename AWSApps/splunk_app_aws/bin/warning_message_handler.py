__author__ = 'frank'

import json
import splunk.admin as admin
from utils.local_manager import LocalServiceManager
from splunklib.client import Entity
from dao.kvstore_access_object import KVStoreAccessObject

import utils.app_util as util
logger = util.get_logger()

DEFAULT_OWNER = 'nobody'

ARG_PAGE_ROOTS = 'page_roots'

KVSTORE_NAMESPACE = 'warningMessageBlackList_kvstore'

PAGE_ROOT_MAP = {
    'Overview': ['overview', 'usage_overview', 'security_overview', 'insights_overview'],
    'Topology': ['topology'],
    'Timeline': ['resource_timeline'],
    'Usage': ['instance_usage', 'individual_instance_usage', 'ebs_usage', 'individual_ebs_usage', 'elb_usage', 'individual_elb_usage', 'rds', 'capacity_planner', 'ri_recommendation', 'ri_inventory', 'lambda_usage'],
    'Security': ['network_acls', 'security_groups', 'iam', 'key_pairs', 'elb_access_logs', 'cloudfront_access_logs', 's3_access_logs', 's3_data_event', 'vpcs', 'vpc_flow_logs_traffic', 'vpc_flow_logs_security', 'resource_activity', 'user_activity'],
    'Insights': ['config_rules', 'inspector', 'ec2_insights','eip_insights', 'elb_insights', 'ebs_insights', 'sg_insights', 'personal_health'],
    'Billing': ['estimated_billing', 'monthly_billing', 'detailed_billing', 'budget_planner']
}


class WarningMessageHandler(admin.MConfigHandler):
    def __init__(self, scriptMode, ctxInfo):
        admin.MConfigHandler.__init__(self, scriptMode, ctxInfo)
        session_key = self.getSessionKey()
        service = LocalServiceManager(util.APP_NAME, DEFAULT_OWNER, session_key).get_local_service()
        self.username = Entity(service, 'authentication/current-context').content['username']
        self.kao = KVStoreAccessObject(KVSTORE_NAMESPACE, session_key)
        self.existed_black_list = json.loads(self.kao.query_items({'username': self.username}))
        self.shouldAutoList = False

    def setup(self):
        for arg in [ARG_PAGE_ROOTS]:
            self.supportedArgs.addOptArg(arg)

    def handleRemove(self, confInfo):
        page_remove = self.callerArgs.id
        page_root_remove = None
        for root in PAGE_ROOT_MAP:
            if page_remove in PAGE_ROOT_MAP[root]:
                page_root_remove = root
                break

        if page_root_remove is None:
            return

        # if not exist, insert directly
        if len(self.existed_black_list) == 0:
            self.kao.insert_single_item({
                'username': self.username,
                'blacklist': [page_root_remove]
            })
        # else, update
        else:
            black_list = self.existed_black_list[0]['blacklist']
            if page_root_remove not in black_list:
                self.kao.update_item_by_key(self.existed_black_list[0]['_key'], {
                    'username': self.username,
                    'blacklist': black_list + [page_root_remove]
                })

        return

    def handleList(self, confInfo):
        results = confInfo['user_pages']

        page_roots = []

        # search black list from kvstore
        self.existed_black_list = json.loads(self.kao.query_items({'username': self.username}))
        if len(self.existed_black_list) > 0:
            page_roots = self.existed_black_list[0]['blacklist']

        results.append('page_roots', page_roots)

        pages = []

        for root in page_roots:
            pages += PAGE_ROOT_MAP[root]

        results.append('pages', pages)

        return

    def handleCreate(self, confInfo):
        if self.callerArgs[ARG_PAGE_ROOTS][0] is None:
            page_roots = []
        else:
            page_roots = self.callerArgs[ARG_PAGE_ROOTS][0].split(',')

        # if not exist, insert directly
        if len(self.existed_black_list) == 0:
            self.kao.insert_single_item({
                'username': self.username,
                'blacklist': page_roots
            })
        # else, update
        else:
            self.kao.update_item_by_key(self.existed_black_list[0]['_key'], {
                'username': self.username,
                'blacklist': page_roots
            })

        return


admin.init(WarningMessageHandler, admin.CONTEXT_APP_ONLY)