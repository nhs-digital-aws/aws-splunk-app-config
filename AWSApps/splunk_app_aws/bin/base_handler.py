__author__ = 'michael'

import splunk.admin as admin
import utils.app_util as util

logger = util.get_logger()


class BaseHandler(admin.MConfigHandler):
    def setup(self, readonly_public = False):
        # By default it is "false", which means the sub-handlers also can not process GET requests when user does not meet the validation rules.
        # When it is set to "true", the "handleList" method can be invoked even current user is not power.
        if self.requestedAction == admin.ACTION_LIST and readonly_public:
            return
        util.validate_aws_admin(self.getSessionKey())

    def _log_request(self):
        logger.info('action %s name %s args %s' % (self.requestedAction, self.callerArgs.id, self.callerArgs))
