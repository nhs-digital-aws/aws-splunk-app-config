"""
Custom REST Endpoint for enumerating AWS S3 Bucket.
"""

import aws_bootstrap_env

import threading
import urllib
import splunk
import splunk.admin
from botocore.exceptions import ClientError

from splunktaucclib.rest_handler.error import RestError
import splunk_ta_aws.common.proxy_conf as pc
from splunk_ta_aws.common.s3util import connect_s3
import splunk_ta_aws.common.ta_aws_consts as tac

import splunk_ta_aws.common.ta_aws_common as tacommon
from solnlib.splunkenv import get_splunkd_uri


def timed(timeout, func, default=None, args=(), kwargs={}):
    """
    Run func with the given timeout. If func didn't finish running
    within the timeout, raise TimeLimitExpired
    """

    class FuncThread(threading.Thread):
        def __init__(self):
            threading.Thread.__init__(self)
            self.result = default
            self.error = None

        def run(self):
            try:
                self.result = func(*args, **kwargs)
            except Exception, exc:
                self.error = exc

    it = FuncThread()
    it.start()
    it.join(timeout)
    if it.error:
        raise RestError(400, it.error)
    return it.result


def all_buckets(s3_conn):
    return s3_conn.get_all_buckets()


class ConfigHandler(splunk.admin.MConfigHandler):

    def setup(self):
        self.supportedArgs.addReqArg('aws_account')
        self.supportedArgs.addOptArg('aws_iam_role')

    def handleList(self, confInfo):
        aws_account = None
        aws_account_category = tac.RegionCategory.COMMERCIAL

        if self.callerArgs['aws_account'] is not None:
            aws_account = self.callerArgs['aws_account'][0]

        aws_iam_role = None
        if self.callerArgs.get('aws_iam_role') is not None:
            aws_iam_role = self.callerArgs['aws_iam_role'][0]

        if not aws_account:
            confInfo['bucket_name'].append('bucket_name', [])
            return

        # Set proxy for boto3
        proxy = pc.get_proxy_info(self.getSessionKey())
        tacommon.set_proxy_env(proxy)

        cred_service = tacommon.create_credentials_service(
            get_splunkd_uri(), self.getSessionKey())

        try:
            cred = cred_service.load(aws_account, aws_iam_role)
            aws_account_category = cred.category
        except ClientError as err:
            raise RestError(400, str(err.message) + '. Please make sure the AWS Account and Assume Role are correct.')

        host_name = tac.CATEGORY_HOST_NAME_MAP[aws_account_category]

        connection = connect_s3(
            cred.aws_access_key_id, cred.aws_secret_access_key,
            self.getSessionKey(), host_name,
            security_token=cred.aws_session_token,
        )

        rs = timed(25, all_buckets, [], (connection,))
        rlist = []
        for r in rs:
            rlist.append(r.name)

        for bucket in rlist:
            confInfo[bucket].append('bucket_name', bucket)
            confInfo[bucket].append('host_name', host_name)


def main():
    splunk.admin.init(ConfigHandler, splunk.admin.CONTEXT_NONE)


if __name__ == '__main__':
    main()
