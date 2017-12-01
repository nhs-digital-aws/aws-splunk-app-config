import splunk.admin as admin
import json
import utils.app_util as util
from dao.kvstore_access_object import KVStoreAccessObject
import recommendation_task.recommendation_consts as recomm_consts

logger = util.get_logger()


ARG_RECOMM_ID = 'recomm_id'
ARG_FEEDBACK = 'feedback'
ARG_TIMESTAMP = 'timestamp'

ARG_RESOURCE_ID = 'resource_id'
ARG_FEATURE = 'feature'
ARG_PRIORITY = 'ml_priority'
ARG_ACTION = 'ml_action'
ARG_DIMENSION = 'ml_dimension'


"""
@api {get} /saas-aws/splunk_app_aws_recomm_action list recommendation feedbacks
@apiName list-recommendation-feedbacks
@apiGroup Recommendation Feedbacks
@apiSuccess {Atom.Entry} entry recommendation feedbacks
"""

"""
@api {post} /saas-aws/splunk_app_aws_recomm_action create a recommendation feedback
@apiName create-recommendation-feedback
@apiGroup Recommendation Feedbacks
@apiSuccess {Atom.Entry} entry recommendation feedbacks
"""


class RecommActionHandler(admin.MConfigHandler):
    def __init__(self, scriptMode, ctxInfo):
        admin.MConfigHandler.__init__(self, scriptMode, ctxInfo)
        self.shouldAutoList = False
        self.kao = KVStoreAccessObject(recomm_consts.FEEDBACK_COLLECTION, self.getSessionKey())
        self.recomm_kao = KVStoreAccessObject(recomm_consts.RECOMMENDATION_COLLECTION, self.getSessionKey())

    def setup(self):
        for arg in []:
            self.supportedArgs.addReqArg(arg)
        for arg in [ARG_RECOMM_ID, ARG_FEEDBACK, ARG_TIMESTAMP]:
            self.supportedArgs.addOptArg(arg)

    def handleList(self, confInfo):
        results = self.kao.query_items({
            'splunk_account': self.userName
        }, 'timestamp')

        results = json.loads(results)

        for result in results:
            d = confInfo[result['_key']]
            for key in result.keys():
                d.append(key, result[key])

        logger.info('list %s recommendation feedbacks' % (len(results)))

        return

    def handleEdit(self, confInfo):
        recomm_id = self.callerArgs[ARG_RECOMM_ID][0]
        item = self._merge_details(recomm_id)

        if not item:
            logger.info('failed to update feedback for %s' % recomm_id)
            return False

        logger.info('update feedback %s to %s' % (item[ARG_RESOURCE_ID], item[ARG_FEEDBACK]))

        return self.kao.update_item_by_key(self.callerArgs.id, item)

    def handleCreate(self, confInfo):
        recomm_id = self.callerArgs[ARG_RECOMM_ID][0]
        item = self._merge_details(recomm_id)

        if not item:
            logger.info('failed to create %s feedback for %s' % (self.callerArgs[ARG_FEEDBACK][0], recomm_id))
            return False

        new_item = self.kao.insert_single_item(item)
        new_item = json.loads(new_item)
        confInfo[new_item['_key']].append('id', item)

        logger.info('create feedback for %s' % (item[ARG_RESOURCE_ID]))

        return new_item

    def _merge_details(self, recomm_id):
        item = {}

        try:
            item = json.loads(self.recomm_kao.get_item_by_key(recomm_id))
        except:
            logger.info('failed to find recomm_item %s' % recomm_id)
            return False

        feedback_item = {}

        for key in [ARG_RESOURCE_ID, ARG_DIMENSION, ARG_FEATURE, ARG_PRIORITY, ARG_ACTION]:
            feedback_item[key] = item[key]

        feedback_item[ARG_RECOMM_ID] = recomm_id
        feedback_item['splunk_account'] = self.userName
        feedback_item[ARG_FEEDBACK] = self.callerArgs[ARG_FEEDBACK][0]
        feedback_item[ARG_TIMESTAMP] = int(self.callerArgs[ARG_TIMESTAMP][0]) / 1000
        return feedback_item

admin.init(RecommActionHandler, admin.CONTEXT_APP_ONLY)