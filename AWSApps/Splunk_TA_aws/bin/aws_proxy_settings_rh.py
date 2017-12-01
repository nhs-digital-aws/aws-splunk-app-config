import aws_bootstrap_env

import re
import logging
import splunk.admin as admin
from splunktalib.rest_manager import util, error_ctl
from splunk_ta_aws.common.proxy_conf import ProxyManager

KEY_NAMESPACE = util.getBaseAppName()
KEY_OWNER = '-'

AWS_PROXY = 'aws_proxy'

POSSIBLE_KEYS = ('host', 'port', 'username', 'password', 'proxy_enabled')


class ProxyRestHandler(admin.MConfigHandler):
    def __init__(self, scriptMode, ctxInfo):
        admin.MConfigHandler.__init__(self, scriptMode, ctxInfo)

        if self.callerArgs.id and self.callerArgs.id != 'aws_proxy':
            error_ctl.RestHandlerError.ctl(1202, msgx='aws_proxy', logLevel=logging.INFO)

    def setup(self):
        if self.requestedAction in (admin.ACTION_CREATE, admin.ACTION_EDIT):
            for arg in POSSIBLE_KEYS:
                self.supportedArgs.addOptArg(arg)
        return

    def handleCreate(self, confInfo):
        try:
            args = self.validate(self.callerArgs.data)

            args_dict = {}

            for arg in POSSIBLE_KEYS:
                if arg in args:
                    args_dict[arg] = args[arg][0]
                else:
                    args_dict[arg] = ''

            proxy_str = '%s:%s@%s:%s' % (args_dict['username'], args_dict['password'], args_dict['host'], args_dict['port'])

            if 'proxy_enabled' in args:
                enable = True if args_dict['proxy_enabled'] == '1' else False
            else:
                proxy = self.get()
                enable = True if (proxy and proxy.get_enable()) else False
            self.update(proxy_str, enable)
        except Exception as exc:
            error_ctl.RestHandlerError.ctl(400, msgx=exc, logLevel=logging.INFO)

    def handleList(self, confInfo):
        try:
            proxy = self.get()
            if not proxy:
                confInfo[AWS_PROXY].append('proxy_enabled', '0')
                return
            m = re.match('^(?P<username>\S*):(?P<password>\S*)@(?P<host>\S+):(?P<port>\d+$)', proxy.get_proxy())
            if not m:
                confInfo[AWS_PROXY].append('proxy_enabled', '0')
                return

            groupDict = m.groupdict()
            confInfo[AWS_PROXY].append('username', groupDict['username'])
            confInfo[AWS_PROXY].append('password', groupDict['password'])
            confInfo[AWS_PROXY].append('host', groupDict['host'])
            confInfo[AWS_PROXY].append('port', groupDict['port'])
            confInfo[AWS_PROXY].append('proxy_enabled', proxy.get_enable() and '1' or '0')
        except Exception as exc:
            error_ctl.RestHandlerError.ctl(400, msgx=exc, logLevel=logging.INFO)
        return

    def validate(self, args):
        if 'proxy_enabled' in args and args['proxy_enabled'][0] not in ('0', '1'):
            error_ctl.RestHandlerError.ctl(1100, msgx='proxy_enabled={}'.format(args['proxy_enabled'][0]),
                                           logLevel=logging.INFO)
        return args

    def get(self):
        pm = ProxyManager(self.getSessionKey())
        proxy = pm.get_proxy()
        return proxy

    def update(self, proxy, enable):
        try:
            pm = ProxyManager(self.getSessionKey())
            pm.set(proxy, str(enable).lower())
        except Exception as exc:
            error_ctl.RestHandlerError.ctl(400, msgx=exc, logLevel=logging.INFO)


if __name__ == "__main__":
    admin.init(ProxyRestHandler, admin.CONTEXT_NONE)