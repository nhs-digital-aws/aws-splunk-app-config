import aws_bootstrap_env
import splunk.admin as admin
from splunk_ta_aws.common.local_manager import LocalServiceManager
import splunklib.client as client
import splunk_ta_aws.common.ta_aws_consts as tac

REST_URI_MAP = {
    'aws_proxy': 'splunk_ta_aws/splunk_ta_aws_settings_proxy',
    'logging': 'splunk_ta_aws/splunk_ta_aws_settings_%s/%s'
}

LOGGING_ENDPOINTS = {
    'billing': 'logging',
    'config': 'logging',
    'cloudtrail': 'logging',
    'cloudwatch': 'logging',
    's3': 'logging',
    's3_incremental': 'splunk_ta_aws_logs',
    'description': 'logging',
    'cloudwatch_logs': 'logging',
    'kinesis': 'logging',
    'inspector': 'logging',
    'config_rule': 'logging',
    'sqs': 'logging',
    's3sqs': 'logging'
}

OPTIONAL_ARGS = ['proxy_enabled', 'host', 'port', 'username', 'password']


class SettingsHandler(admin.MConfigHandler):
    def __init__(self, *args, **kwargs):
        admin.MConfigHandler.__init__(self, *args, **kwargs)
        self._service = LocalServiceManager(app=tac.splunk_ta_aws, session_key=self.getSessionKey()).get_local_service()
        self._object_id = self.callerArgs.id

    def setup(self):
        for arg in OPTIONAL_ARGS + LOGGING_ENDPOINTS.keys():
            self.supportedArgs.addOptArg(arg)
        return

    def handleList(self, confInfo):
        result = confInfo[self._object_id]
        uri = REST_URI_MAP[self._object_id]

        if self._object_id == 'aws_proxy':
            entity = client.Entity(self._service, uri)

            for key in entity.content.keys():
                if key != 'password':
                    result[key] = entity[key]

        elif self._object_id == 'logging':
            for service in LOGGING_ENDPOINTS.keys():
                entity = client.Entity(self._service, uri % (service, LOGGING_ENDPOINTS[service]))
                result[service] = entity['level']

        result['eai:appName'] = tac.splunk_ta_aws
        result['eai:userName'] = 'nobody'
        result.setMetadata(admin.EAI_ENTRY_ACL, {'owner': 'nobody', 'app': tac.splunk_ta_aws})

        return

    def handleEdit(self, confInfo):
        uri = REST_URI_MAP[self._object_id]

        if self._object_id == 'aws_proxy':
            query = {}
            for arg in self.callerArgs.data:
                if self.callerArgs.data[arg][0]:
                    query[arg] = self.callerArgs.data[arg][0]
            query['name'] = self._object_id

            entity = client.Entity(self._service, uri)
            entity.post(**query)

        elif self._object_id == 'logging':
            for arg in self.callerArgs.data:
                if arg in LOGGING_ENDPOINTS.keys():
                    entity = client.Entity(self._service, uri % (arg, LOGGING_ENDPOINTS[arg]))
                    entity.post(level=self.callerArgs.data[arg][0])

        return


admin.init(SettingsHandler, admin.CONTEXT_APP_ONLY)