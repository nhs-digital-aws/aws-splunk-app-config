'''
Usage:
    python aws_config_cli.py -h

The usage is pretty similar to `aws cli` which is service oriented

Examples:
1. Create AWS account on `hfw-01`
$ python aws_config_cli.py account create --hostname hfw-01 --config-file config_examples/account-settings.json

2. Dry run, validate S3 data inputs configuration
$ python aws_config_cli.py s3 create --hostname hfw-01 --config-file config_examples/s3-inputs.json --dry-run

3. Create S3 data inputs on `hfw-01`
$ python aws_config_cli.py s3 create --hostname hfw-01 --config-file config_examples/s3-inputs.json

4. List all S3 data inputs on `hfw-01`
$ python aws_config_cli.py s3 list --hostname hfw-01

5. List specific S3 data inputs on `hfw-01`
$ python aws_config_cli.py s3 list --hostname hfw-01 --names s3-01

6. Delete S3 data inputs specified on `hfw-01`
$ python aws_config_cli.py s3 delete --hostname hfw-01 --names s3-01

7. Delete 2 AWS account on `hfw-01`
$ python aws_config_cli.py account delete --hostname hfw-01 --name aws-account-0,aws-account-1

8. Create all data inptus and settings in one shot
$ python aws_config_cli.py all create --config-file config_examples/all.json
'''

from __future__ import absolute_import
import argparse
import json
import copy


# Add Splunk_TA_aws/bin to sys.path to make this tool runable without
# user to setup PYTHONPATH etc

import sys
import os.path as op
cur_dir = op.dirname(op.abspath(__file__))
bindir = op.dirname(op.dirname(cur_dir))
sys.path.append(bindir)

import aws_bootstrap_env
_ = aws_bootstrap_env

import splunksdc.log as logging
import config
import app_config

APPNAME = 'Splunk_TA_aws'

logger = logging.get_context_logger('configuration_tool')


def _setup_logger(logger):
    factory = logging.StreamHandlerFactory()
    formatter = logging.ContextualLogFormatter(True)
    logging.RootHandler.setup(factory, formatter)
    logger.setLevel(logging.INFO)


class AwsConfigCli(object):

    def __init__(self, params, appname, splunk_info_file, spec_dir):
        self.params = params
        self.appname = appname
        self.splunks = config.load_splunks(splunk_info_file)
        self.rest_api_specs = config.load_rest_api_specs(spec_dir)
        self.endpoint = self._get_endpoint()
        self.config_mgr = app_config.AppConfigManager(
            self.splunks, self.appname)

    def __call__(self):
        if self.params.action == 'create':
            self.create()
        elif self.params.action == 'delete':
            self.delete()
        else:
            self.list()

    def create(self):
        endpoint_name = self.params.resource
        if self.params.resource == 'all':
            endpoint_name = None
            hostname = None
        else:
            hostname = self.params.hostname

        host_stanzas = config.load_configs(
            self.params.config_file, self.splunks, self.rest_api_specs,
            rest_endpoint_name=endpoint_name, hostname=hostname)

        if self.params.dry_run:
            logger.info('In dry run mode, only validate configurations. '
                        'If no error message shows, validation passes')
            return

        for host_stanza in host_stanzas:
            endpoint = host_stanza.rest_endpoint
            with logging.LogContext(hostname=host_stanza.hostname,
                                    endpoint=endpoint, action='create'):
                try:
                    self.config_mgr.create(
                        endpoint, host_stanza.hostname,
                        host_stanza.stanzas)
                except app_config.AppConfigException:
                    # Swallow this exception and carry on
                    continue

    def delete(self):
        names = self.params.names.split(',')
        self.config_mgr.delete(self.endpoint, self.params.hostname, names)

    def list(self):
        names = None
        if self.params.names:
            names = self.params.names.split(',')
        results = self.config_mgr.list(
            self.endpoint, self.params.hostname, names)
        items = []
        for result in results:
            item = copy.deepcopy(result['content'])
            item['name'] = result['name']
            items.append(item)
        print json.dumps(items, indent=2)

    def _get_endpoint(self):
        if self.params.resource == 'all':
            # endpoint will be specified in conf file
            return None

        spec = self.rest_api_specs.get(self.params.resource)
        if not spec:
            logger.error('No rest API spec is found for resource',
                         resource=self.params.resource)
            raise ValueError('Invalid params')

        return spec.endpoint


def _get_aws_addon_resources():
    return {
        's3': 'modinput data input',
        'incr-s3': 'modinput data input',
        'sqs-based-s3': 'modinput data input',
        'kinesis': 'modinput data input',
        'description': 'modinput data input',
        'inspector': 'modinput data input',
        'config': 'modinput data input',
        'account': 'AWS account setting',
        'iam-role': 'AWS IAM role setting',
    }


def _add_create_all_option(subparsers):
    help_msg = ('Create all resources specified in conf file which can contain'
                ' different resources and different hostnames')
    subparser = subparsers.add_parser('all', help=help_msg)

    # create
    action_subparsers = subparser.add_subparsers(dest='action')
    create_parser = action_subparsers.add_parser(
        'create', help='Create all data inputs and/or settings')

    help_msg = ('Stanza configuration file, refer to config_examples/all.json '
                'for example')
    create_parser.add_argument(
        '--config-file', dest='config_file', required=True, help=help_msg)
    create_parser.add_argument(
        '--dry-run', dest='dry_run', action='store_true',
        help='Dry run just validate the configurations')


def compose_cli_args():
    parser = argparse.ArgumentParser(description='AWS AddOn configuration tool')

    # Modinput or setting subcommands
    subparsers = parser.add_subparsers(
        dest='resource', help='Pick which resource to manipulate')
    resources = _get_aws_addon_resources()
    for resource, desc in resources.iteritems():
        help_msg = '{} {} subcommand'.format(resource, desc)
        subparser = subparsers.add_parser(resource, help=help_msg)

        # create, list, delete subcommands
        action_subparsers = subparser.add_subparsers(dest='action')

        # create
        create_parser = action_subparsers.add_parser(
            'create', help='Create {}'.format(desc))
        help_msg = ('Stanza configuration file, refer to '
                    'config_examples/s3-inputs.json for example')
        create_parser.add_argument(
            '--hostname', dest='hostname', required=True,
            help='Splunk hostname')
        create_parser.add_argument(
            '--config-file', dest='config_file', required=True, help=help_msg)
        create_parser.add_argument(
            '--dry-run', dest='dry_run', action='store_true',
            help='Dry run just validate the configurations')

        # list
        list_parser = action_subparsers.add_parser(
            'list', help='List {}'.format(desc))
        list_parser.add_argument(
            '--hostname', dest='hostname', required=True,
            help='Splunk hostname')

        help_msg = ('List {} by names. `names` are separated by `,`.'
                    'For example, \'s3_prod1,s3_prod2\'. if omit this '
                    'argument, list all').format(desc)
        list_parser.add_argument(
            '--names', dest='names', required=False, help=help_msg)

        # delete
        delete_parser = action_subparsers.add_parser(
            'delete', help='Delete {}'.format(desc))
        delete_parser.add_argument(
            '--hostname', dest='hostname', required=True,
            help='Splunk hostname')

        help_msg = ('Delete {} by names. `names` are separated by `,`.'
                    'For example, \'s3_prod1,s3_prod2\'.').format(desc)
        delete_parser.add_argument(
            '--names', dest='names', required=True, help=help_msg)

    _add_create_all_option(subparsers)

    args = parser.parse_args()
    return args


def main():
    _setup_logger(logger)
    args = compose_cli_args()

    splunk_info_file = op.join(cur_dir, 'splunk-info.json')
    spec_dir = op.join(cur_dir, 'rest_specs')

    cli = AwsConfigCli(args, APPNAME, splunk_info_file, spec_dir)
    cli()


if __name__ == '__main__':
    main()
