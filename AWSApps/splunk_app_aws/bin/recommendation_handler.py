import splunk.admin as admin
import json
from dao.kvstore_access_object import KVStoreAccessObject
import recommendation_config.dependency_checker as recomm_utils
import recommendation_task.recommendation_consts as recomm_consts
import utils.app_util as util

logger = util.get_logger()


"""
@api {get} /saas-aws/splunk_app_aws_recommendation list recommendation items
@apiName list-recommendation-items
@apiGroup Recommendation
@apiSuccess {Atom.Entry} entry recommendation items
"""
class RecommendationHandler(admin.MConfigHandler):
    def __init__(self, scriptMode, ctxInfo):
        admin.MConfigHandler.__init__(self, scriptMode, ctxInfo)
        self.shouldAutoList = False
        self.kao = KVStoreAccessObject(recomm_consts.RECOMMENDATION_COLLECTION, self.getSessionKey())

    def setup(self):
        return

    def handleList(self, confInfo):
        session_key = self.getSessionKey()

        if recomm_utils.is_splunk_light(session_key):
            logger.info('ML lib does not exist in Splunk Light.')
            raise admin.ArgValidationException('Not supported in Splunk Light')

        if not recomm_utils.is_ml_lib_included(session_key):
            logger.info('ML lib does not exist')
            raise admin.ArgValidationException('ML lib does not exist')

        results = self.kao.query_items()

        results = json.loads(results)

        for result in results:
            d = confInfo[result['_key']]
            for key in result.keys():
                d.append(key, result[key])

        logger.info('list %s recommendation' % (len(results)))
        
        return

admin.init(RecommendationHandler, admin.CONTEXT_APP_ONLY)