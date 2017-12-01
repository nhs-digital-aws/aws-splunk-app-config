__author__ = 'pezhang'

from anomaly_detection.service.anomaly_conf_manager import AnomalyConfManager
from anomaly_detection.service.search_queue_manager import SearchQueueManager
import splunk.Intersplunk as intersplunk
import traceback
from utils.local_manager import LocalServiceManager

DEFAULT_APP_NAME = 'splunk_app_aws'
DEFAULT_OWNER = 'nobody'

try:
    search_results, dummyresults, settings = intersplunk.getOrganizedResults()
    session_key = settings['sessionKey']
    service = LocalServiceManager(DEFAULT_APP_NAME, DEFAULT_OWNER, session_key).get_local_service()

    conf_manager = AnomalyConfManager(service)
    search_queue_manager = SearchQueueManager(service)
    searches = conf_manager.get_jobs()
    search_queue_manager.run_searches(searches)
except:
    stack = traceback.format_exc()
    results = intersplunk.generateErrorResults("Error : Traceback: " + str(stack))
    intersplunk.outputResults(results)
