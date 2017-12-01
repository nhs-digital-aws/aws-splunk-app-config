__author__ = 'frank'

import sys
import splunk.Intersplunk as intersplunk
import utils.app_util as util
from utils.local_manager import LocalServiceManager
import splunk.search as search


# results of spl
results = []


try:
    # get session key
    results,dummyresults,settings = intersplunk.getOrganizedResults()
    session_key = settings['sessionKey']

    # generate local service
    service = LocalServiceManager(app=util.APP_NAME, session_key=session_key).get_local_service()

    if len(sys.argv) == 2:
        lookup_name = sys.argv[1]

        spl = '| inputlookup %s' % lookup_name

        # get search restrictions of current user
        search_restriction_arr = util.get_search_restrictions(session_key)

        if len(search_restriction_arr) > 0:
            search_restrictions = ' OR '.join(search_restriction_arr)
            spl = '%s | search %s' % (spl, search_restrictions)

        util.get_logger().info(spl)

        results = search.searchAll(spl, sessionKey = session_key)

except:
    import traceback
    stack = traceback.format_exc()
    results = intersplunk.generateErrorResults("Error : Traceback: " + str(stack))
    util.get_logger().error(str(stack))

intersplunk.outputResults(results)