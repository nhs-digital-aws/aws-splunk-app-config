import time

import splunktalib.common.util as scutil
import aws_description_consts as adc
import splunk_ta_aws.common.ta_aws_consts as tac
import splunksdc.log as logging


logger = logging.get_module_logger()


def get_supported_description_apis():
    import ec2_description as ade
    import elb_description as aed
    import vpc_description as avd
    import cloudfront_description as acd
    import rds_description as ard
    import lambda_description as ald
    import s3_description as asd
    import iam_description as aid

    return {
        "ec2_instances": ade.ec2_instances,
        "ec2_reserved_instances": ade.ec2_reserved_instances,
        "ebs_snapshots": ade.ec2_ebs_snapshots,
        "ec2_volumes": ade.ec2_volumes,
        "ec2_security_groups": ade.ec2_security_groups,
        "ec2_key_pairs": ade.ec2_key_pairs,
        "ec2_images": ade.ec2_images,
        "ec2_addresses": ade.ec2_addresses,
        "elastic_load_balancers": aed.classic_load_balancers, # forward-compatibility
        "classic_load_balancers": aed.classic_load_balancers,
        "application_load_balancers": aed.application_load_balancers,
        "vpcs": avd.vpcs,
        "vpc_subnets": avd.vpc_subnets,
        "vpc_network_acls": avd.vpc_network_acls,
        "cloudfront_distributions": acd.cloudfront_distributions,
        "rds_instances": ard.rds_instances,
        "lambda_functions": ald.lambda_functions,
        "s3_buckets": asd.s3_buckets,
        "iam_users": aid.iam_users
    }


class DescriptionDataLoader(object):

    def __init__(self, task_config):
        """
        :task_config: dict object
        {
        "interval": 30,
        "api": "ec2_instances" etc,
        "source": xxx,
        "sourcetype": yyy,
        "index": zzz,
        }
        """

        self._task_config = task_config
        self._supported_desc_apis = get_supported_description_apis()
        self._api = self._supported_desc_apis.get(task_config[adc.api], None)
        if self._api is None:
            logger.error("Unsupported service.",
                         service=task_config[adc.api],
                         ErrorCode="ConfigurationError",
                         ErrorDetail="Service is unsupported.",
                         datainput=task_config[tac.datainput])

    def __call__(self):
        with logging.LogContext(datainput=self._task_config[tac.datainput]):
            self.index_data()

    def index_data(self):
        logger.info("Start collecting description for service=%s, region=%s",
                    self._task_config[adc.api], self._task_config[tac.region])
        try:
            self._do_index_data()
        except Exception:
            logger.exception("Failed to collect description data for %s.",
                             self._task_config[adc.api])
        logger.info("End of collecting description for service=%s, region=%s",
                    self._task_config[adc.api], self._task_config[tac.region])

    def _do_index_data(self):
        if self._api is None:
            return

        evt_fmt = ("<stream><event>"
                   "<time>{time}</time>"
                   "<source>{source}</source>"
                   "<sourcetype>{sourcetype}</sourcetype>"
                   "<index>{index}</index>"
                   "<data>{data}</data>"
                   "</event></stream>")

        task = self._task_config
        results = self._api(task)

        events = []
        size_total = 0
        for result in results:
            event = evt_fmt.format(source=task[tac.source],
                                   sourcetype=task[tac.sourcetype],
                                   index=task[tac.index],
                                   data=scutil.escape_cdata(result),
                                   time=time.time())
            size_total += len(event)
            events.append(event)
        logger.info("Send data for indexing.",
                    action="index",
                    size=size_total,
                    records=len(events))

        task["writer"].write_events("".join(events))

    def get_interval(self):
        return self._task_config[tac.interval]

    def stop(self):
        pass

    def get_props(self):
        return self._task_config
