__author__ = 'frank'

import splunk.admin as admin
import utils.app_util as util
from splunklib.client import Entity
from utils.local_manager import LocalServiceManager


class CurrentContextHandler(admin.MConfigHandler):
    def setup(self):
        pass

    def handleList(self, confInfo):
        session_key = self.getSessionKey()
        service = LocalServiceManager(app=util.APP_NAME, session_key=session_key).get_local_service()

        current_context = Entity(service, 'authentication/current-context')

        roles = current_context.content['roles']
        capabilities = current_context.content['capabilities']

        confInfo['current_context'].append('roles', roles)
        confInfo['current_context'].append('capabilities', capabilities)
        confInfo['current_context'].append('username', current_context.content['username'])
        confInfo['current_context'].append('is_admin', 'admin_all_objects' in capabilities or 'admin' in roles)
        confInfo['current_context'].append('is_aws_admin', util.is_aws_admin(session_key))

        return


admin.init(CurrentContextHandler, admin.CONTEXT_APP_ONLY)