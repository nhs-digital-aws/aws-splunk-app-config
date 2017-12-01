
"""
Modular Input for AWS CloudTrail
"""
import sys
import os
import os.path as op

import splunk_ta_aws.common.ta_aws_consts as taconsts

from aws_cloudtrail_data_loader import Input
import solnlib.modular_input.event_writer as cew
from splunk_ta_aws.common.ta_aws_consts import splunk_ta_aws
from splunktalib.common.util import extract_datainput_name

from splunksdc.environ import get_checkpoint_folder

# This import is required to using k-v logging
import splunksdc.log as logging

from splunklib import modularinput as smi

modular_name = 'splunk_ta_aws_cloudtrail'

logger = logging.get_module_logger()


modular_args = {
    'name': {
        'title': 'Name',
        'description': 'Choose an ID or nickname for this configuration',
        'required_on_create': True
    },
    'aws_account': {
        'title': 'AWS Account',
        'description': 'AWS account',
        'required_on_create': True,
        'required_on_edit': True
    },
    'aws_region': {
        'title': 'SQS Queue Region',
        'description':
            'Name of the AWS region in which the notification queue is '
            'located. Regions should be entered as e.g., us-east-1, '
            'us-west-2, eu-west-1, ap-southeast-1, etc.',
        'required_on_create': True,
        'required_on_edit': True
    },
    'sqs_queue': {
        'title': 'SQS Queue Name',
        'description':
            'Name of queue to which notifications of new CloudTrail logs are '
            'sent. CloudTrail logging should be configured to publish to an '
            'SNS topic. The queue should be subscribed to the topics that '
            'notify of the desired logs. Note that multiple topics from '
            'different regions can publish to a single queue if desired.',
        'required_on_create': True,
        'required_on_edit': True
    },
    'exclude_describe_events': {
        'title': 'Exclude \'Describe*\' events',
        'description':
            'Do not index \'Describe\' events. These events typically '
            'constitute a high volume of calls, and indicate read-only '
            'requests for information.',
        'data_type': smi.Argument.data_type_boolean,
        'required_on_create': False
    },
    'remove_files_when_done': {
        'title': 'Remove log files when done',
        'description':
            'Delete log files from the S3 bucket once they have been read '
            'and sent to the Splunk index',
        'data_type': smi.Argument.data_type_boolean,
        'required_on_create': False
    },
    'blacklist': {
        'title': 'Blacklist for Describe events',
        'description':
            'PCRE regex for specifying event names to be excluded. '
            'Leave blank to use the default set of read-only event names',
        'required_on_create': False
    },
    'excluded_events_index': {
        'title': 'Excluded events index',
        'description':
            'Optional index in which to write the excluded events. '
            'Leave blank to use the default of simply deleting events. '
            'Specified indexes must be created in Splunk for this to '
            'be effective.',
        'required_on_create': False
    }
}




class CloudTrailInput(smi.Script):

    def __init__(self):
        super(CloudTrailInput, self).__init__()
        self._canceled = False
        self._ew = None

    def get_scheme(self):
        """overloaded splunklib modularinput method"""

        scheme = smi.Scheme('AWS CloudTrail')
        scheme.description = (
            'Collect and index log files produced by AWS CloudTrail. '
            'CloudTrail logging must be enabled and published to SNS topics '
            'and an SQS queue.'
        )
        scheme.use_external_validation = True
        scheme.streaming_mode_xml = True
        scheme.use_single_instance = False

        # Add arguments
        for name, arg in modular_args.iteritems():
            scheme.add_argument(
                smi.Argument(
                    name,
                    title=arg.get('title'),
                    validation=arg.get('validation'),
                    data_type=arg.get(
                        'data_type',
                        smi.Argument.data_type_string,
                    ),
                    description=arg.get('description'),
                    required_on_create=arg.get('required_on_create', False),
                    required_on_edit=arg.get('required_on_edit', False),
                )
            )
        return scheme

    def validate_input(self, definition):
        """overloaded splunklib modularinput method"""
        pass

    def stream_events(self, inputs, ew):
        ew = cew.ClassicEventWriter()
        """overloaded splunklib modularinput method"""
        input_name, input_items = inputs.inputs.popitem()
        stanza_name = extract_datainput_name(input_name)
        logging.setup_root_logger(app_name=splunk_ta_aws, modular_name='cloudtrail', stanza_name=stanza_name)
        Input(
            self._input_definition.metadata[taconsts.server_uri],
            self._input_definition.metadata[taconsts.session_key],
            self._input_definition.metadata[taconsts.checkpoint_dir],
            input_name, input_items, ew
        ).run()


def delete_ckpt(input_name):
    ckpt_dir = get_checkpoint_folder('aws_cloudtrail')
    ckpt_file = op.join(ckpt_dir, input_name + '.v3.ckpt')
    if op.isfile(ckpt_file):
        os.remove(ckpt_file)
        logger.info('Checkpoint file is deleted: %s' % ckpt_file)


def main():
    # Force Enable SIGV4 for S3
    if "S3_USE_SIGV4" not in os.environ:
        os.environ["S3_USE_SIGV4"] = "True"

    exitcode = CloudTrailInput().run(sys.argv)
    sys.exit(exitcode)
