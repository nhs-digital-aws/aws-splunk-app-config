__author__ = 'pezhang'

import anomaly_detection.anomaly_detection_const as const
from anomaly_detection.service.anomaly_conf_manager import AnomalyConfManager
from dao.kvstore_access_object import KVStoreAccessObject
import json
import migration_const
import utils.app_util as util
import uuid

logger = util.get_logger()

class KVStoreToConfMigrationManager(object):
    """
        Handle anomaly detection settings migration from kvstore to configuration file
        and data from "aws_anomaly_detection" index to "main" index with "anomaly detection" source
    """
    def __init__(self, service, session_key, kvstore_name=migration_const.KVSTORE_NAMESPACE, conf_name=const.CONF_NAME):
        """
            :param  service: used to initialize configuration handler and search jobs
            :param session_key: used to initialize kvstore handler
            :param kvstore_name: the name of kv store which stored anomaly detection rule settings
            :param conf_name: the name of conf file which stored job settings

        """
        self.service = service
        self.jobs = service.jobs
        self.conf_manager = AnomalyConfManager(self.service, conf_name)
        self.kao = KVStoreAccessObject(kvstore_name, session_key)

    def migrate(self):
        anomaly_detection_rules = json.loads(self.kao.query_items())
        if len(anomaly_detection_rules) == 0:
            logger.info('Anomaly Detection Migration: no need to migrate.')
            return []  # empty kvstore

        migrate_stanza_name_list = []
        # get existed jobs' searches and names from anomaly configuration file
        anomaly_configs = self.conf_manager.conf.list()
        searches = []
        names = []
        for config in anomaly_configs:
            content = config.content()
            if migration_const.JOB_NAME in content and migration_const.JOB_SEARCH in content:
                searches.append(content[migration_const.JOB_SEARCH])
                names.append(content[migration_const.JOB_NAME])

        for rule in anomaly_detection_rules:
            # migrate from kvstore to configuration file
            stanza_name, settings = self._migrate_settings(rule, searches, names)
            if stanza_name is None:
                # if the search is existed, continue
                logger.info('Anomaly Detection Migration: KVstore object with key %s has been migrated before.' % (
                    rule['_key']))
            else:
                # save job and migrate data
                self.conf_manager.create_stanza(stanza_name, settings)
                names.append(settings['job_name'])
                searches.append(settings['job_search'])
                logger.info(
                    'Anomaly Detection Migration: KVstore object with key %s has been migrated to conf file with stanza name %s' % (
                        rule['_key'], stanza_name))

                # migrate from "aws_anomaly_detection" index to "summary" index
                job = self._migrate_data(rule, stanza_name)
                logger.info('Anomaly Detection Migration: data migration with job sid %s and isFail %s' % (
                    job['sid'], job['isFailed']))

            # clear kvstore
            self.kao.delete_item_by_key(rule['_key'])

            migrate_stanza_name_list.append(stanza_name)

        return [x for x in migrate_stanza_name_list if x is not None]

    def _migrate_settings(self, rule, searches, names):
        is_billing = rule['category'] == 'billing'
        spl = migration_const.KVSTORE_TO_CONF_SPL[rule['category']][rule['granularity']]
        service_display_name = 'all' if rule['service'] == '*' else rule['service']
        response = '' if is_billing else rule['parameters'].split('=')[1]
        search = spl.format(rule['anomalyAccount'], rule['service'], service_display_name, response)
        if search in searches:
            return None, None

        granularity_display_name = 'daily' if rule['granularity'] == 'd' else 'hourly'
        response_display_name = 'response=all' if response == '*' else 'response=' + response
        if is_billing:
            response_display_name = ''
        job_name = '{0} {1} {2} {3} {4}'.format(rule['category'], rule['anomalyAccount'], service_display_name,
                                                granularity_display_name, response_display_name)

        train = '10' + rule['granularity']
        schedule = 'Hourly' if rule['granularity'] == 'h' else 'Daily'

        return str(uuid.uuid1()), {
            'job_name': job_name,
            'job_train': train,
            'job_schedule': schedule,
            'job_priority': migration_const.DEFAULT_PRIORIY,
            'job_search': search,
            'job_mode': migration_const.DEFAULT_MODE
        }

    def _migrate_data(self, rule, job_id):
        service = 'all' if rule['service'] == '*' else rule['service']
        parameters_regex = 'response=\*' if rule['parameters'].find('*') >= 0 else rule['parameters']
        migrate_data_spl = migration_const.DATA_MIGRATE_SPL.format(
            '{0}_{1}_{2}'.format(rule['anomalyAccount'], rule['category'], rule['service']), rule['granularity'],
            parameters_regex, job_id, service, const.INDEX,
            const.SOURCE_TYPE)
        job = self.jobs.create(migrate_data_spl)
        return job
