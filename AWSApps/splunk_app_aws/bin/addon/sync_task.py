import os
import csv
import utils.app_util as util
import splunk.util as splunk_util
import splunk.search as splunk_search
from utils.local_manager import LocalServiceManager

logger = util.get_logger()

DEFAULT_APP_NAME = 'splunk_app_aws'
DEFAULT_OWNER = 'nobody'

ACCOUNT_HEADER = ['account_id', 'name']
ACCOUNT_LOOKUP_NAME = 'all_account_ids.csv'
ACCOUNT_LOOKUP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'lookups', ACCOUNT_LOOKUP_NAME)

# key is sourcetype, value is macro name.
SOURCETYPE_MACRO_MAP = {
    'aws:cloudtrail': 'aws-cloudtrail-index',
    'aws:config': 'aws-config-index',
    'aws:config:rule': 'aws-config-rule-index',
    'aws:cloudwatch': 'aws-cloudwatch-index',
    'aws:cloudwatchlogs:vpcflow': 'aws-cloudwatch-logs-index',
    'aws:description': 'aws-description-index',
    'aws:billing': 'aws-billing-index',
    'aws:s3': 'aws-s3-index',
    'aws:s3:accesslogs': 'aws-s3-index',
    'aws:cloudfront:accesslogs': 'aws-s3-index',
    'aws:elb:accesslogs': 'aws-s3-index',
    'aws:inspector': 'aws-inspector-index',
    'aws:sqs': 'aws-sqs-index'
}

# SCHEDULE_SEARCHES will be scheduled when ANY type of inputs added/updated.
SCHEDULE_SEARCHES = ['CloudTrail EventName Generator', 'AWS Billing - Account Name',
                     'Config: Topology Daily Snapshot Generator', 'Config: Topology History Appender',
                     'Config: Topology Monthly Snapshot Generator', 'Config: Topology Playback Appender',
                     'AWS Description - Tags','AWS Config - Tags', 'AWS Description - CloudFront Edges', 'AWS Description - S3 Buckets',
                     'CloudWatch: Topology CPU Metric Generator', 'CloudWatch: Topology Disk IO Metric Generator', 'CloudWatch: Topology Network Traffic Metric Generator',
                     'CloudWatch: Topology Volume IO Metric Generator', 'CloudWatch: Topology Volume Traffic Metric Generator',
                     'Billing: Topology Billing Metric Generator', 'Amazon Inspector: Topology Amazon Inspector Recommendation Generator',
                     'Config Rules: Topology Config Rules Generator', 'Billing: Billing Reports S3Key Generator', 'Insights: EBS', 'Insights: EIP', 'Insights: ELB', 'Insights: SG', 'Insights: IAM',
                     'VPC Flow Logs Summary Generator - Dest IP', 'VPC Flow Logs Summary Generator - Dest Port', 'VPC Flow Logs Summary Generator - Src IP',
                     'Anomaly Detection: Jobs Service', 'Anomaly Detection: Schedule Time Checker']


class SyncTask(object):
    def __init__(self, session_key):
        logger.info('initing SyncTask...')

        self.session_key = session_key
        self.local_service = LocalServiceManager(DEFAULT_APP_NAME, DEFAULT_OWNER, self.session_key).get_local_service()

    def sync_accounts(self):
        """Summary
            Sync account id, name from add-on and save/update them to a lookup file.
        """
        logger.info('syncing accounts...')

        # get the existed accounts in the lookup file
        updated_account_list = []
        existed_account_keys = {}
        key_pattern = '%s%s'

        if os.path.isfile(ACCOUNT_LOOKUP_PATH):
            with open(ACCOUNT_LOOKUP_PATH) as csv_file:
                reader = csv.DictReader(csv_file)
                for row in reader:
                    account_id = row['account_id']
                    account_name = row['name']

                    key = key_pattern % (account_id, account_name)
                    existed_account_keys[key] = True
                    updated_account_list.append({
                        'account_id': account_id,
                        'name': account_name
                    })

        # check the newest accounts from summary index, append the new ones
        accounts_spl = util.get_option_from_conf(self.session_key, 'macros', 'aws-account-summary', 'definition')
        account_list = splunk_search.searchAll('%s | dedup name, account_id | table name, account_id' % accounts_spl, sessionKey = self.session_key)
        logger.info('%s account(s) in total' % len(account_list))

        is_accounts_changed = False

        for account in account_list:
            account_id = account.get('account_id')[0].value
            account_name = account.get('name')[0].value

            if key_pattern % (account_id, account_name) not in existed_account_keys:
                updated_account_list.append({
                    'account_id': account_id,
                    'name': account_name
                })
                is_accounts_changed = True

        # update lookup file
        if is_accounts_changed:
            util.update_lookup_file(self.session_key, ACCOUNT_LOOKUP_NAME, ACCOUNT_HEADER, updated_account_list)

        return 'Accounts Synchronization Complete.'

    def sync_macros(self):
        """Summary
            Sync inputs for update macros based on custom indexes.
        """
        logger.info('syncing inputs...')

        # get the snapshot of current inputs from summary index
        inputs_spl = util.get_option_from_conf(self.session_key, 'macros', 'aws-sourcetype-index-summary', 'definition')
        input_list = splunk_search.searchAll(inputs_spl, sessionKey = self.session_key)
        logger.info('%s input(s) in total' % len(input_list))

        for input in input_list:
            index_name = input.get('input_index')[0].value
            sourcetype = input.get('input_sourcetype')[0].value

            # update macros
            if sourcetype in SOURCETYPE_MACRO_MAP:
                macro_stanza = SOURCETYPE_MACRO_MAP[sourcetype]
                util.update_index_macro(self.session_key, macro_stanza, index_name)

        # enable savedsearches
        saved_searches = self.local_service.saved_searches

        for search_name in SCHEDULE_SEARCHES:
            if search_name in saved_searches:
                search = saved_searches[search_name]
                enabled = splunk_util.normalizeBoolean(search.content['is_scheduled'])
                if not enabled:
                    search.update(**{'is_scheduled': 1})

        return 'Macros Update Complete.'
