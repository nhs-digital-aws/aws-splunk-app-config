import aws_bootstrap_env
import splunk.admin as admin
import splunktalib.common.pattern as scp
from splunksdc import log as logging
import splunk_ta_aws.common.ta_aws_consts as tac
import splunk_ta_aws.common.ta_aws_common as tacommon
import splunk_ta_aws.common.proxy_conf as pc
import splunk_ta_aws.modinputs.kinesis.aws_kinesis_common as akc
from solnlib.splunkenv import get_splunkd_uri


logger = logging.get_module_logger()


class KinesisStreams(admin.MConfigHandler):
    valid_params = [tac.region, tac.account]

    def setup(self):
        for param in self.valid_params:
            self.supportedArgs.addOptArg(param)
        self.supportedArgs.addOptArg(tac.aws_iam_role)

    @scp.catch_all(logger)
    def handleList(self, conf_info):
        logger.info("start listing kinesis streams")
        for required in self.valid_params:
            if not self.callerArgs or not self.callerArgs.get(required):
                logger.error('Missing "%s"', required)
                raise Exception('Missing "{}"'.format(required))

        aws_account = ""
        if self.callerArgs[tac.account] is not None:
            aws_account = self.callerArgs[tac.account][0]

        aws_iam_role = None
        if self.callerArgs.get(tac.aws_iam_role) is not None:
            aws_iam_role = self.callerArgs[tac.aws_iam_role][0]

        # Set proxy for boto3
        proxy = pc.get_proxy_info(self.getSessionKey())
        tacommon.set_proxy_env(proxy)

        cred_service = tacommon.create_credentials_service(
            get_splunkd_uri(), self.getSessionKey())
        cred = cred_service.load(aws_account, aws_iam_role)

        proxy[tac.server_uri] = get_splunkd_uri()
        proxy[tac.session_key] = self.getSessionKey()
        proxy[tac.aws_account] = aws_account
        proxy[tac.aws_iam_role] = aws_iam_role
        proxy[tac.region] = self.callerArgs[tac.region][0]
        proxy[tac.key_id] = cred.aws_access_key_id
        proxy[tac.secret_key] = cred.aws_secret_access_key
        proxy['aws_session_token'] = cred.aws_session_token
        client = akc.KinesisClient(proxy, logger)
        streams = client.list_streams()

        for stream in streams:
            conf_info[stream].append("stream_names", stream)

        logger.info("end of listing kinesis streams")


def main():
    admin.init(KinesisStreams, admin.CONTEXT_NONE)


if __name__ == "__main__":
    main()
