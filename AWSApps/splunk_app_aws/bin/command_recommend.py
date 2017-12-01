import sys
import splunk.Intersplunk as intersplunk
from recommendation_task.unused_sg_task import UnusedSecurityGroupTask
from recommendation_task.ec2_usage_task import EC2UsageTask
from recommendation_task.elb_usage_task import ElbUsageTask

results = []

# stores Task constructors
task_pool = {
    'unused_sg': UnusedSecurityGroupTask,
    'ec2_usage': EC2UsageTask,
    'elb_usage': ElbUsageTask
}

# labels for tasks, shown in results
task_labels = {
    'unused_sg': 'Unused Security Groups',
    'ec2_usage': 'Upgrade/Downgrade EC2 Instances',
    'elb_usage': 'Unused ELBs'
}

# results of spl
results = []


# execute task
def _execute_task(task_name, session_key):
    Task = task_pool[task_name]
    task = Task(session_key)

    task.pre_execute()
    output = task.execute()
    task.post_execute()

    results.append({
        'Task Name': task_labels[task_name],
        'Task Result': output
    })


try:
    # get session key
    results,dummyresults,settings = intersplunk.getOrganizedResults()
    session_key = settings['sessionKey']

    # execute tasks
    if len(sys.argv) == 1:
        for name in task_pool:
            _execute_task(name, session_key)
    else:
        for name in sys.argv:
            name = name.lower()
            if name in task_pool:
                _execute_task(name, session_key)

except:
    import traceback
    stack = traceback.format_exc()
    results = intersplunk.generateErrorResults("Error : Traceback: " + str(stack))

intersplunk.outputResults(results)
