import os


class SplunkEnviron(object):
    def __init__(self, environ=None):
        if not environ:
            environ = os.environ
        self._home = environ.get('SPLUNK_HOME', os.getcwd())

    def get_splunk_home(self):
        return self._home

    def get_log_folder(self):
        path = os.path.join(self._home, 'var', 'log', 'splunk')
        return path

    def get_checkpoint_folder(self, schema):
        path = os.path.join(self._home, 'var', 'lib', 'splunk', 'modinputs', schema)
        return path

_environ = SplunkEnviron()


def get_log_folder():
    return _environ.get_log_folder()


def get_checkpoint_folder(schema):
    return _environ.get_checkpoint_folder(schema)
