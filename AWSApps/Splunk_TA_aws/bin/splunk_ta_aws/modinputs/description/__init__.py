#!/usr/bin/python

"""
This is the main entry point for AWS Description TA
"""

import time
import aws_description_consts as adcon
import splunksdc.log as logging
import splunktalib.data_loader_mgr as dlm
import splunk_ta_aws.common.ta_aws_consts as tac
import splunk_ta_aws.common.ta_aws_common as tacommon
import aws_description_conf as adc
import aws_description_data_loader as addl


logger = logging.get_module_logger()


def print_scheme():
    title = "AWS Description Metadata"
    description = "Collect and index descriptions for AWS services"
    tacommon.print_scheme(title, description)


def _do_run():
    meta_configs, _, tasks = tacommon.get_configs(
        adc.AWSDescribeConf, "aws_description", logger)

    if not tasks:
        logger.info("No data input has been configured, exiting...")
        return

    meta_configs[tac.log_file] = adcon.description_log
    loader_mgr = dlm.create_data_loader_mgr(meta_configs)
    tacommon.setup_signal_handler(loader_mgr, logger)
    conf_change_handler = tacommon.get_file_change_handler(loader_mgr, logger)
    conf_monitor = adc.create_conf_monitor(conf_change_handler)
    loader_mgr.add_timer(conf_monitor, time.time(), 10)

    jobs = [addl.DescriptionDataLoader(task) for task in tasks]
    loader_mgr.run(jobs)


def run():
    """
    Main loop. Run this TA forever
    """

    logger.info("Start aws_description")
    try:
        _do_run()
    except Exception:
        logger.exception("Failed to collect description data.")
    logger.info("End aws_description")


def main():
    """
    Main entry point
    """
    # description is single-instance, output to one log file
    logging.setup_root_logger(app_name=tac.splunk_ta_aws, modular_name=adcon.mod_name)
    tacommon.main(print_scheme, run)


if __name__ == "__main__":
    main()
