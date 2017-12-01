import os
import platform
import stat
import sys
import subprocess
import json
import recommendation_task.recommendation_consts as const
import tempfile
import utils.app_util as util
logger = util.get_logger()

def execute_ml_process(process_py_name, json_arg):
    """Execute the current Python script using the Anaconda Python
    interpreter included with Splunk_SA_Scientific_Python.

    After executing this function, you can safely import the Python
    libraries included in Splunk_SA_Scientific_Python (e.g. numpy).
    """

    if 'Continuum' in sys.version:
        fix_sys_path()
        reload(os)
        reload(platform)
        reload(stat)
        reload(sys)
        reload(subprocess)
        return

    supported_systems = {
        ('Linux', 'i386'): 'linux_x86',
        ('Linux', 'x86_64'): 'linux_x86_64',
        ('Darwin', 'x86_64'): 'darwin_x86_64',
        ('Windows', 'AMD64'): 'windows_x86_64'
    }

    system = (platform.system(), platform.machine())
    if system not in supported_systems:
        raise Exception('Platform not supported by Splunk_SA_Scientific_Python: %s %s' % (system))

    sa_path = os.path.join(os.environ['SPLUNK_HOME'], 'etc', 'apps', 'Splunk_SA_Scientific_Python_%s' % (supported_systems[system]))
    if not os.path.isdir(sa_path):
        raise Exception('Failed to find Splunk_SA_Scientific_Python_%s' % (supported_systems[system]))

    system_path = os.path.join(sa_path, 'bin', '%s' % (supported_systems[system]))

    if system[0] == 'Windows':
        python_path = os.path.join(system_path, 'python.exe')
    else:
        python_path = os.path.join(system_path, 'bin', 'python')

    # Ensure that execute bit is set on .../bin/python
    if system[0] != 'Windows':
        mode = os.stat(python_path).st_mode
        os.chmod(python_path, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    ml_py_path = os.path.join(const.APP_BIN_PATH, 'machine_learning_mod', process_py_name)

    # use file to record json arguments, or it may cause OS Error: Argument list too long
    arg_file_path = os.path.join(tempfile.gettempdir(), process_py_name.split('.')[0] + '.arguments')
    arg_file = open(arg_file_path, 'w')
    arg_file.write(json.dumps(json_arg))
    arg_file.close()

    ml_process = subprocess.Popen([python_path, ml_py_path, process_py_name.split('.')[0]], stdout=subprocess.PIPE)

    (stdoutput, erroutput) = ml_process.communicate()

    logger.info('Machine Learning Results: %s' % stdoutput)
    logger.error(erroutput)

    return json.loads(stdoutput)


def fix_sys_path():
    # Update sys.path to move Splunk's PYTHONPATH to the end.
    pp = os.environ.get('PYTHONPATH', None)
    if not pp: return
    for spp in pp.split(os.pathsep):
        try:
            sys.path.remove(spp)
            sys.path.append(spp)
        except: pass
