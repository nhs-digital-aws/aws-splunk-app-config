__author__ = 'peter'

import splunk.admin as admin
import splunklib.results as results
import utils.app_util as util
import json
from utils.local_manager import LocalServiceManager
from program_timer import ProgramTimer

logger = util.get_logger()
UNLIMITED = -1


class UsageHandler(admin.MConfigHandler):
    def setup(self):
        pass

    @classmethod
    def _get_index_volume_by_sourcetype(cls, splunk_service):
        index_volume_by_sourcetype = 'search index=summary earliest=-7d@d latest=@d report=aws_indexed_data_volume | timechart span=1d useother=f max(sum_mb) as volume by series | fillnull value=0 | eval time = strftime(_time, "%F") | fields - _time, _span, _spandays'
        search_results = splunk_service.jobs.oneshot(index_volume_by_sourcetype)
        reader = results.ResultsReader(search_results)

        return list(reader)

    def handleList(self, conf_info):
        self._log_request()
        pt = ProgramTimer("collect usage data")

        service_manager = LocalServiceManager(app=self.appName, owner=self.userName, session_key=self.getSessionKey())
        local_service = service_manager.get_local_service()

        data_ingested = self._get_index_volume_by_sourcetype(local_service)

        usages = []
        for data_per_day in data_ingested:
            usage = dict()
            usage['time'] = data_per_day.pop('time')
            usage['volumes'] = data_per_day
            usages.append(usage)

        all_usage = dict()
        all_usage['usage'] = usages

        conf_info['default']['value'] = json.dumps(all_usage)

        pt.stop()
        return

    def _log_request(self):
        logger.info('action %s name %s args %s' % (self.requestedAction, self.callerArgs.id, self.callerArgs))


admin.init(UsageHandler, admin.CONTEXT_APP_ONLY)