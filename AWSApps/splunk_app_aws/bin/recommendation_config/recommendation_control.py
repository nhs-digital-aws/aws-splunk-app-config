__author__ = 'frank'

from utils.local_manager import LocalServiceManager

import utils.app_util as util
logger = util.get_logger()

SAVEDSEARCH_NAME = 'Machine Learning: Recommendation'


def disable_recommend_job(session_key):
    recommendation_saved_search = _get_recommendation_saved_search(session_key)
    recommendation_saved_search.update(disabled = True).refresh()
    return


def enable_recommend_job(session_key):
    recommendation_saved_search = _get_recommendation_saved_search(session_key)
    recommendation_saved_search.update(disabled = False).refresh()
    return


def start_recommend_job(session_key):
    recommendation_saved_search = _get_recommendation_saved_search(session_key)
    recommendation_saved_search.update(disabled = False).refresh()
    recommendation_saved_search.dispatch()
    return


def update_recommend_job(session_key, *command_params):
    recommendation_saved_search = _get_recommendation_saved_search(session_key)
    recommend_spl = '|recommend'
    for param in command_params:
        recommend_spl = '%s %s' % (recommend_spl, param)
    recommendation_saved_search.update(search = recommend_spl).refresh()
    return


def _get_recommendation_saved_search(session_key):
    service = LocalServiceManager(app=util.APP_NAME, session_key=session_key).get_local_service()
    return service.saved_searches[SAVEDSEARCH_NAME]