__author__ = 'pezhang'

import anomaly_detection.anomaly_detection_const as const
import service_const


class AnomalyJob(object):
    """
        Build anomaly detection job object according to contents from "anomalyconfigs" configuration file
    """

    def __init__(self, id, content):
        """
            :param id: job id
            :param content: attributes for a giving job id
        """
        is_content_valid = True
        self.content = {}
        for key in service_const.SEARCH_KEYS:
            if key not in content:
                is_content_valid = False
                break
            else:
                self.content[key] = content[key]

        for key in service_const.SEARCH_INT_KEYS:
            if key not in content:
                is_content_valid = False
                break
            else:
                try:
                    self.content[key] = int(content[key])
                except ValueError:
                    is_content_valid = False
                    break

        if not is_content_valid:
            raise ValueError()

        is_job_enabled = (self.content['job_mode'] & const.ENABLE_MODE) > 0
        if not is_job_enabled:
            raise AttributeError()

        self.id = id
        self._parse_schedule()
        self._parse_search()

    def _parse_schedule(self):
        if self.content['job_schedule'] == 'Hourly':
            self.content['search_earliest'] = '-h@h-' + self.content['job_train']
            self.content['search_latest'] = '@h'
        elif self.content['job_schedule'] == 'Daily':
            self.content['search_earliest'] = '-d@d-' + self.content['job_train']
            self.content['search_latest'] = '@d'
        elif self.content['job_schedule'] == 'Weekly':
            self.content['search_earliest'] = '-7d@d-' + self.content['job_train']
            self.content['search_latest'] = '@d'
        else:
            self.content['search_earliest'] = '-mon@d-' + self.content['job_train']
            self.content['search_latest'] = '@d'

    def _parse_search(self):
        is_detected_mode = (self.content['job_mode'] & const.DETECT_MODE) > 0
        anomaly_search_spl = '| anomalyviz ' if is_detected_mode else ''
        self.content['actual_search'] = self.content['job_search'] \
                                        + '{0} | eval job_id="{1}" | collect index="{2}" sourcetype="{3}"'.format(
            anomaly_search_spl, self.id, const.INDEX, const.SOURCE_TYPE)

    def get_search(self):
        return self.content['actual_search']

    def get_priority(self):
        return self.content['job_priority']

    def get_id(self):
        return self.id

    def get_earliest_latest(self):
        return {'earliest_time': self.content['search_earliest'], 'latest_time': self.content['search_latest']}
