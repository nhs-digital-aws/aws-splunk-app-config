import sys
import json
import traceback

from splunklib.searchcommands import dispatch, StreamingCommand
from splunklib.searchcommands import Configuration, Option
from splunktalib.common import util


from splunk_ta_aws.modalerts.sns.aws_sns_publisher import SNSPublisher, SNSMessageContent
import splunksdc.log as logging

logger = logging.get_module_logger()
logger.setLevel(logging.INFO)

util.remove_http_proxy_env_vars()


@Configuration()
class AwsSnsAlertCommand(StreamingCommand, SNSPublisher):
    account = Option(require=True)
    region = Option(require=True)
    topic_name = Option(require=True)
    publish_all = Option(require=False)

    def stream(self, records):
        logger.info('Search Alert - Started')
        splunkd_uri = self.search_results_info.splunkd_uri
        session_key = self.search_results_info.auth_token
        publish_all = util.is_true(self.publish_all or 'false')

        err = 0
        count = 0
        for i, rec in enumerate(records):
            try:
                count += 1
                yield self._handle_record(splunkd_uri, session_key, rec, i)
            except Exception as exc:
                err += 1
                yield self._handle_error(exc, traceback.format_exc(), rec, i)
            if not publish_all:
                break

        if err:
            self.write_error('%s in %s events failed. '
                             'Check response events for detail' % (err, count))

    def _handle_record(self, splunkd_uri, session_key, record, serial):
        resp = self.publish(splunkd_uri, session_key, self.account,
                            self.region, self.topic_name, record=record)

        result = {'result': 'Success', 'response': json.dumps(resp)}
        res = AwsSnsAlertCommand.make_event(**result)
        logger.debug('Search Alert', **result)
        return {'_serial': serial, '_time': record.get('_time'), '_raw': res}

    def _handle_error(self, exc, tb, record, serial):
        logger.error('Search Alert', result='Failed', error=tb)
        res = AwsSnsAlertCommand.make_event('Failed', error=exc)
        return {'_serial': serial, '_time': record.get('_time'), '_raw': res}

    @staticmethod
    def make_event(result, **kwargs):
        event = 'Search Alert - result="{result}"'.format(result=result)
        arr = ['%s="%s"' % (key, val) for key, val in kwargs.iteritems()]
        arr.insert(0, event)
        return', '.join(arr)

    def make_subject(self, *args, **kwargs):
        return 'Splunk - Alert from Search'

    def make_message(self, *args, **kwargs):
        record = kwargs['record']
        return SNSMessageContent(
            message=record.get('message', ''),
            timestamp=record.get('timestamp', record.get('_time')),
            entity=record.get('entity', ''),
            correlation_id=record.get('record', self.search_results_info.sid),
            source=record.get('source', ''),
            event=record.get('event', record.get('_raw')),
            search_name='',
            results_link='',
            app=self.search_results_info.ppc_app,
            owner=self.search_results_info.ppc_user,
        )


def main():
    factory = logging.StreamHandlerFactory()
    formatter = logging.ContextualLogFormatter(True)
    logging.RootHandler.setup(factory, formatter)
    dispatch(AwsSnsAlertCommand, sys.argv, sys.stdin, sys.stdout)
