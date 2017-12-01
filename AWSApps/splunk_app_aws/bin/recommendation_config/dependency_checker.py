__author__ = 'frank'

import re
from utils.local_manager import LocalServiceManager

ML_APP_NAME = 'Splunk_SA_Scientific_Python*'


def is_ml_lib_included(session_key):
    pattern = re.compile(ML_APP_NAME)
    service = LocalServiceManager(session_key=session_key).get_local_service()
    for app in service.apps:
        app_name = app.name
        if pattern.match(app_name):
            return True
    return False

def is_splunk_light(session_key):
    service = LocalServiceManager(session_key=session_key).get_local_service()
    product_type = service.info()['product_type']
    return product_type == 'lite' or product_type == 'lite_free'