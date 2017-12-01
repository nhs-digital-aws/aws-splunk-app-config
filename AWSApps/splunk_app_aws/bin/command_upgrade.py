import splunk.Intersplunk as intersplunk
import splunklib.client as client
from utils.local_manager import LocalServiceManager
from data_model.data_model import upgrade_421
from data_model.data_model import upgrade_500
from data_model.data_model import upgrade_510
from data_model.data_model import instance_hour_upgrade_510
from anomaly_detection.migration.kvstore_to_conf import KVStoreToConfMigrationManager
import utils.app_util as util
logger = util.get_logger()

import splunk.search as search
import splunk.util as splunkutil
from time import sleep


DEFAULT_APP_NAME = 'splunk_app_aws'
DEFAULT_OWNER = 'nobody'
DATAMODEL_REST = 'datamodel/model'
MODEL_STANZA_NAME = 'datamodel'

UNKNOWN_VERSION = 'unknown'
CURRENT_VERSION = '5.1.0'

TOPOLOGY_SAVEDSEARCHES = ['Config: Topology Daily Snapshot Generator', 'Config: Topology History Appender',
                     'Config: Topology Monthly Snapshot Generator', 'Config: Topology Playback Appender',
                     'AWS Description - Tags','AWS Config - Tags', 'CloudWatch: Topology CPU Metric Generator',
                     'CloudWatch: Topology Disk IO Metric Generator', 'CloudWatch: Topology Network Traffic Metric Generator',
                     'CloudWatch: Topology Volume IO Metric Generator', 'CloudWatch: Topology Volume Traffic Metric Generator',
                     'Billing: Topology Billing Metric Generator', 'Amazon Inspector: Topology Amazon Inspector Recommendation Generator',
                     'Config Rules: Topology Config Rules Generator']

VPC_FLOW_SAVEDSEARCHES = ['VPC Flow Logs Summary Generator - Dest IP', 'VPC Flow Logs Summary Generator - Dest Port', 'VPC Flow Logs Summary Generator - Src IP']

CLOUDFRONT_SAVEDSEARCHES = ['AWS Description - CloudFront Edges']


def _upgrade_datamodel(service, results):
    collection = client.Collection(service, DATAMODEL_REST)
    models = collection.list(search='name=Detailed_Billing')
    result = ''

    if len(models) == 1:
        detailed_model = models[0]

        origin_description = detailed_model.content.description

        updated_description = upgrade_421(origin_description)
        updated_description = upgrade_500(updated_description)
        updated_description = upgrade_510(updated_description)

        if origin_description != updated_description:
            detailed_model.update(**{'description': updated_description})
            result += 'Detailed_Billing'

    models = collection.list(search='name=Instance_Hour')

    if len(models) == 1:
        instance_hour_model = models[0]

        origin_description = instance_hour_model.content.description

        updated_description = instance_hour_upgrade_510(origin_description)

        if origin_description != updated_description:
            instance_hour_model.update(**{'description': updated_description})
            result += 'Instance_Hour'

    if result == '':
        result = 'Nothing needs to be migrated'

    results.append({
        'name': 'Detailed Billing/Instance Hour',
        'description': result
    })

    return results

def _upgrade_topology(service, session_key, results):
    # get data from topology summary index
    topology_results = search.searchAll('search index=aws_topology_history | head 1', sessionKey = session_key)

    # check Config inputs
    is_input_existed = _is_input_existed(session_key, 'aws:config')

    description = ''

    if len(topology_results) == 0:
        _migrate_topology(service)
        _generate_topology_snapshot(service)
        description += 'Migrated existed topology to summary index. Generated topology snapshot. '

    if is_input_existed:
        _enable_savedsearches(service, TOPOLOGY_SAVEDSEARCHES)
        description += 'Enabled corresponding savedsearches.'

    if description is not '':
        results.append({
            'name': 'Topology',
            'description': description
        })

    return


def _upgrade_vpc_flow_log(service, session_key, results):
    # check VPC Flow Log inputs
    is_input_existed = _is_input_existed(session_key, 'aws:cloudwatchlogs')

    if is_input_existed:
        _enable_savedsearches(service, VPC_FLOW_SAVEDSEARCHES)

        results.append({
            'name': 'VPC Flow Log',
            'description': 'Enabled corresponding savedsearches.'
        })

    return


def _upgrade_cloudfront(service, session_key, results):
    # check Cloudfront inputs
    is_input_existed = _is_input_existed(session_key, 'aws:cloudfront:accesslogs')

    if is_input_existed:
        _enable_savedsearches(service, CLOUDFRONT_SAVEDSEARCHES)

        results.append({
            'name': 'CloudFront Access Log',
            'description': 'Enabled corresponding savedsearches.'
        })

    return


def _migrate_topology(service):
    migrate_job = service.saved_searches['Config: Topology History Generator'].dispatch()
    while not migrate_job.is_done():
        sleep(1)
    return


def _generate_topology_snapshot(service):
    service.saved_searches['Config: Topology Daily Snapshot Generator'].dispatch()
    return


def _is_input_existed(session_key, sourcetype):
    input_spl = util.get_option_from_conf(session_key, 'macros', 'aws-input-summary', 'definition')
    results = search.searchAll('%s | search sourcetype="%s"' % (input_spl, sourcetype), sessionKey = session_key)
    return len(results) > 0


def _enable_savedsearches(service, savedsearches):
    for search_name in savedsearches:
        if search_name in service.saved_searches:
            search = service.saved_searches[search_name]
            enabled = splunkutil.normalizeBoolean(search.content['is_scheduled'])
            if not enabled:
                search.update(**{'is_scheduled': 1})
    return

def _upgrade_anomaly_detection(service, session_key, results):
    # delete related stanza of v 5.0 anomaly detection
    recommendation_conf = service.confs['recommendation']
    if 'anomaly_detection' in recommendation_conf:
        recommendation_conf.delete('anomaly_detection')

    migration_manager = KVStoreToConfMigrationManager(service, session_key)
    migrate_stanza_name_list = migration_manager.migrate()
    migrate_message = 'Nothing needs to be migrated'
    if len(migrate_stanza_name_list) > 0:
        migrate_message = '%s has been migrated to anomalyconfigs.conf' %(','.join(migrate_stanza_name_list))
    results.append({
        'name': 'Anomaly detection migration',
        'description': migrate_message
    })

try:
    # get session key
    results,dummyresults,settings = intersplunk.getOrganizedResults()
    session_key = settings['sessionKey']

    service = LocalServiceManager(DEFAULT_APP_NAME, DEFAULT_OWNER, session_key).get_local_service()
    results = []

    # upgrade detailed billing
    _upgrade_datamodel(service, results)

    # upgrade topology
    _upgrade_topology(service, session_key, results)

    # upgrade vpc flow logs
    _upgrade_vpc_flow_log(service, session_key, results)

    # upgrade cloudfront
    _upgrade_cloudfront(service, session_key, results)

    # upgrade anomaly detection
    _upgrade_anomaly_detection(service, session_key, results)

except:
    import traceback
    stack = traceback.format_exc()
    results = intersplunk.generateErrorResults("Error : Traceback: " + str(stack))


intersplunk.outputResults(results)
