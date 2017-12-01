import splunk.entity as entity
import splunklib.client as client

CONF_WEB = 'configs/conf-web'


class LocalServiceManager(object):
    def __init__(self, app=None, owner='nobody', session_key=None, service=None):
        self._app = app
        self._owner = owner
        self._session_key = session_key
        if service is None:
            splunkd_host_port = self._get_entity(CONF_WEB, 'settings').get('mgmtHostPort', '127.0.0.1:8089')
            host_and_port = splunkd_host_port.split(':')
            self.local_splunk_host = host_and_port[0]
            self.local_splunk_port = host_and_port[1]
            self._service = client.Service(host=self.local_splunk_host, port=self.local_splunk_port, app=self._app,
                                           owner=self._owner, token=self._session_key)
        else:
            self._service = service

    def get_local_service(self):
        return self._service

    def _get_entity(self, path, name):
        return entity.getEntity(path, name, sessionKey=self._session_key, namespace=self._app, owner=self._owner)
