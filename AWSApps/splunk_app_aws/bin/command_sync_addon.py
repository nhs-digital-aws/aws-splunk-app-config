import sys
import splunk.Intersplunk as intersplunk

from addon.sync_task import SyncTask
import utils.app_util as util

logger = util.get_logger()

# results of spl
results = []

SYNC_ACCOUNTS_TASK = 'sync_accounts'
SYNC_MACROS_TASK = 'sync_macros'

ALL_TASKS = set([SYNC_ACCOUNTS_TASK, SYNC_MACROS_TASK])


try:
    results,dummyresults,settings = intersplunk.getOrganizedResults()
    session_key = settings['sessionKey']

    tasks = set()

    if len(sys.argv) == 1:
        tasks = ALL_TASKS
    else:
        for task in sys.argv:
            task = task.lower()
            if task in ALL_TASKS:
                tasks.add(task)

    sync_task = SyncTask(session_key)

    # 1. sync accounts
    if SYNC_ACCOUNTS_TASK in tasks:
        result = {
            'Task': 'Sync Accounts'
        }
        try:
            result['Result'] = sync_task.sync_accounts()
        except Exception as err:
            result['Result'] = str(err)
        
        results.append(result)

    # 2. sync inputs for macros update
    if SYNC_MACROS_TASK in tasks:
        result = {
            'Task': 'Sync Macros'
        }
        try:
            result['Result'] = sync_task.sync_macros()
        except Exception as err:
            result['Result'] = str(err)

        results.append(result)


except:
    import traceback
    stack = traceback.format_exc()
    results = intersplunk.generateErrorResults("Error : Traceback: " + str(stack))

intersplunk.outputResults(results)
