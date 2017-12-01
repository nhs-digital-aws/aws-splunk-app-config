__author__='frank'

import splunk.admin as admin
import utils.app_util as util
import re

PREFIX_ARG = 'prefix'
FIELD_ARG = 'field'

class RestrictedSearchTermHandler(admin.MConfigHandler):
    def __init__(self, scriptMode, ctxInfo):
        admin.MConfigHandler.__init__(self, scriptMode, ctxInfo)
        self.shouldAutoList = False

    def setup(self):
        for arg in [PREFIX_ARG, FIELD_ARG]:
            self.supportedArgs.addOptArg(arg)

    def handleList(self, confInfo):
        search_restriction_arr = util.get_search_restrictions(self.getSessionKey())
        prefix = self.callerArgs[PREFIX_ARG][0]
        field = self.callerArgs[FIELD_ARG][0]
        regex_expression = '(?<=[( ])%s\s*=' % field

        new_search_restriction_arr = []

        for search_restriction in search_restriction_arr:
            util.get_logger().info(search_restriction)
            search_restriction, count = re.subn(regex_expression, '%s%s=' % (prefix, field), search_restriction)
            new_search_restriction_arr.append(search_restriction)

        confInfo['search_restrictions'].append('search_restrictions', ' OR '.join(new_search_restriction_arr))
        return


admin.init(RestrictedSearchTermHandler, admin.CONTEXT_APP_ONLY)