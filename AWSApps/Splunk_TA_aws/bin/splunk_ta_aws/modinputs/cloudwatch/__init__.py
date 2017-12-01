#!/usr/bin/python

"""
This is the main entry point for My TA
"""


import time

import splunksdc.log as logging
import splunktalib.common.util as utils
import splunktalib.orphan_process_monitor as opm

import splunk_ta_aws.common.ta_aws_common as tacommon
import splunk_ta_aws.common.ta_aws_consts as tac
import aws_cloudwatch_consts as acc


logger = logging.get_module_logger()


def print_scheme():
    import sys

    scheme = """<scheme>
    <title>AWS CloudWatch</title>
    <description>Collect and index metrics produced by AWS CloudWatch.</description>
    <use_external_validation>true</use_external_validation>
    <use_single_instance>true</use_single_instance>
    <streaming_mode>xml</streaming_mode>
    <endpoint>
        <args>
            <arg name="name">
                <title>Name</title>
                <description>Unique data input name</description>
                <required_on_create>true</required_on_create>
            </arg>
            <arg name="aws_account">
                <title>AWS Account</title>
                <required_on_create>true</required_on_create>
                <required_on_edit>true</required_on_edit>
            </arg>
            <arg name="aws_iam_role">
                <title>Assume Role</title>
                <required_on_create>false</required_on_create>
                <required_on_edit>false</required_on_edit>
            </arg>
            <arg name="aws_region">
                <title>AWS CloudWatch Region</title>
                <required_on_create>true</required_on_create>
                <required_on_edit>true</required_on_edit>
           </arg>
            <arg name="metric_namespace">
                <title>AWS CloudWatch Metric Namespace</title>
                <required_on_create>true</required_on_create>
                <required_on_edit>true</required_on_edit>
           </arg>
            <arg name="metric_names">
                <title>AWS CloudWatch Metric Names</title>
                <required_on_create>true</required_on_create>
                <required_on_edit>true</required_on_edit>
           </arg>
            <arg name="metric_dimensions">
                <title>AWS CloudWatch Metric Dimensions</title>
                <required_on_create>true</required_on_create>
                <required_on_edit>true</required_on_edit>
            </arg>
            <arg name="statistics">
                <title>AWS CloudWatch Metric Statistics</title>
                <required_on_create>true</required_on_create>
                <required_on_edit>true</required_on_edit>
            </arg>
            <arg name="period">
                <title>AWS CloudWatch Metric Granularity</title>
                <required_on_create>true</required_on_create>
                <required_on_edit>true</required_on_edit>
            </arg>
            <arg name="polling_interval">
                <title>Polling interval</title>
                <required_on_create>true</required_on_create>
                <required_on_edit>true</required_on_edit>
            </arg>
        </args>
    </endpoint>
    </scheme>"""
    sys.stdout.write(scheme)


@utils.catch_all(logger, False)
def run():
    """
    Main loop. Run this TA forever
    """

    from aws_cloudwatch_conf import AWSCloudWatchConf, create_conf_monitor
    from splunk_ta_aws.common.aws_concurrent_data_loader import AwsDataLoaderManager

    logger.info("Start Cloudwatch TA")
    metas, stanzas, tasks = tacommon.get_configs(
        AWSCloudWatchConf, "aws_cloudwatch", logger)

    if not tasks:
        return

    loader = AwsDataLoaderManager(tasks, 'splunk_ta_aws', 'cloudwatch')

    conf_change_handler = tacommon.get_file_change_handler(loader, logger)
    conf_monitor = create_conf_monitor(conf_change_handler)
    loader.add_timer(conf_monitor, time.time(), 10)

    orphan_checker = opm.OrphanProcessChecker(loader.stop)
    loader.add_timer(orphan_checker.check_orphan, time.time(), 1)

    # mon = acconf.MetricDimensionMonitor(stanzas, loader.tear_down)
    # freq = int(os.environ.get("cloudwatch_mon", 86400))
    # loader.add_timer(mon.check_changes, time.time() + freq, freq)

    loader.start()
    logger.info("End CloudWatch TA")


def main():
    """
    Main entry point
    """
    # cloudwatch is single instance, output to one log file
    logging.setup_root_logger(app_name=tac.splunk_ta_aws, modular_name=acc.mod_name)
    tacommon.main(print_scheme, run)


if __name__ == "__main__":
    main()
