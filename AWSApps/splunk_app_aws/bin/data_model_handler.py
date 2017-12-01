import splunk.admin as admin
import utils.app_util as util
import splunklib.client as client

from utils.local_manager import LocalServiceManager
from data_model.data_model import update_description

logger = util.get_logger()

ARG_TAGS = 'tags'
DEFAULT_APP_NAME = 'splunk_app_aws'
DEFAULT_OWNER = 'nobody'
DATAMODEL_REST = 'datamodel/model'


"""
@api {post} /saas-aws/splunk_app_aws_data_model update datamodel schema
@apiGroup data model
@apiName update-datamodel
@apiParam {string} tags list of tags
@apiSuccess (201) {Atom.Entry} entry nothing
"""

class DataModelHandler(admin.MConfigHandler):
    def __init__(self, scriptMode, ctxInfo):
        admin.MConfigHandler.__init__(self, scriptMode, ctxInfo)
        self._service = LocalServiceManager(DEFAULT_APP_NAME, DEFAULT_OWNER, self.getSessionKey()).get_local_service()
        self._collection = client.Collection(self._service, DATAMODEL_REST)
        self.shouldAutoList = False

        
    def setup(self):
        util.validate_aws_admin(self.getSessionKey())

        for arg in [ARG_TAGS]:
            self.supportedArgs.addReqArg(arg)


    def handleCreate(self, confInfo):
        tags = self.callerArgs[ARG_TAGS][0]
        tags = tags.split('|') if tags else []

        models = self._collection.list(search='name=Detailed_Billing OR name=Instance_Hour')

        for model in models:
            description = update_description(model.content.description, tags)
            model.update(**{'description': description})

        return

admin.init(DataModelHandler, admin.CONTEXT_APP_ONLY)