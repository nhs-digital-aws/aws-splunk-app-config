
import sys
import json
import logging
import traceback


def parse():
    if len(sys.argv) > 1 and sys.argv[1] == '--execute':
        try:
            return json.loads(sys.stdin.read())
        except:
            print >> sys.stderr, \
                'ERROR Unexpected error: %s' % traceback.format_exc()
            sys.exit(3)
    else:
        print >> sys.stderr, \
            'Argument "--execute" is required: %s. ' % json.dumps(sys.argv)
        sys.exit(2)


class ModularAlert(object):
    """
    Splunk modular alert.
    """

    # contents in payload
    SERVER_URI = 'server_uri'
    SERVER_HOST = 'server_host'
    SESSION_KEY = 'session_key'

    OWNER = 'owner'
    APP = 'app'
    CONFIGURATION = 'configuration'

    SID = 'sid'
    SEARCH_NAME = 'search_name'
    RESULT = 'result'
    RESULTS_FILE = 'results_file'
    RESULTS_LINK = 'results_link'

    def __init__(self, logger, payload):
        self._payload = payload
        self._logger = logger

    def payload(self, name):
        return self._payload[name]

    def result(self, field, default=''):
        result = self.payload(ModularAlert.RESULT)
        return result.get(field, default)

    def param(self, param, default=None):
        return self.payload(ModularAlert.CONFIGURATION).get(param, default)

    def run(self):
        self.log('Started')
        try:
            self._execute()
        except Exception:
            self.exit_with_err(traceback.format_exc())

    def _execute(self):
        """
        Execute alert.

        :return:
        """
        raise NotImplementedError()

    def log(self, msg, level=logging.INFO):
        self._logger.log(
            msg='Modular Alert - %s' % msg,
            level=level
        )

    def exit_with_err(self, msg, status=1):
        self.log('Alert Failed: %s' % msg, level=logging.ERROR)
        sys.exit(status)
