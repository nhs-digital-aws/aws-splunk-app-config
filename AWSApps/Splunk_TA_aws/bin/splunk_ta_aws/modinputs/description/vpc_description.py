import boto.vpc

import splunksdc.log as logging
import splunk_ta_aws.common.ta_aws_consts as tac
import splunk_ta_aws.common.ta_aws_common as tacommon
import description as desc

logger = logging.get_module_logger()


def connect_vpc_to_region(config):
    return desc.BotoRetryWrapper(boto_client=tacommon.connect_service_to_region(
        boto.vpc.connect_to_region, config))


@desc.describe_pagination  # No pagination
@desc.refresh_credentials
def vpcs(config):
    keys = ["cidr_block", "classic_link_enabled", "dhcp_options_id", "id",
            "instance_tenancy", "is_default", "state", "tags"]

    conn = connect_vpc_to_region(config)
    all_vpcs = conn.get_all_vpcs()
    results = desc.pop_description_results(
        all_vpcs, keys, {tac.account_id: config[tac.account_id]})
    return results, {}


@desc.describe_pagination  # No pagination
@desc.refresh_credentials
def vpc_subnets(config):
    keys = ["adefaultForAz", "availability_zone", "available_ip_address_count",
            "cidr_block", "id", "mapPublicIpOnLaunch", "state", "tags",
            "vpc_id"]

    conn = connect_vpc_to_region(config)
    subnets = conn.get_all_subnets()
    results = desc.pop_description_results(
        subnets, keys, {tac.account_id: config[tac.account_id]})
    return results, {}


@desc.describe_pagination  # No pagination
@desc.refresh_credentials
def vpc_network_acls(config):
    keys = ["associations", "default", "id", "network_acl_entries",
            "tags", "vpc_id"]
    asso_keys = ["id", "network_acl_id", "subnet_id"]
    entry_keys = ["cidr_block", "egress", "icmp", "port_range", "protocol",
                  "rule_action", "rule_number"]
    port_keys = ["from_port", "to_port"]
    icmp_keys = ["code", "type"]

    conn = connect_vpc_to_region(config)
    net_acls = conn.get_all_network_acls()

    results = desc.pop_description_results(
        net_acls, keys, {tac.account_id: config[tac.account_id]},
        raw_event=True)

    for i, result in enumerate(results):
        result["associations"] = desc.pop_description_results(
            result["associations"], asso_keys, {}, pop_region_name=False,
            raw_event=True)

        result["network_acl_entries"] = desc.pop_description_results(
            result["network_acl_entries"], entry_keys, {},
            pop_region_name=False, raw_event=True)

        for entry in result["network_acl_entries"]:
            entry["port_range"] = desc.pop_description_result(
                entry, port_keys, {}, pop_region_name=False, raw_event=True)
            entry["icmp"] = desc.pop_description_result(
                entry, icmp_keys, {}, pop_region_name=False, raw_event=True)

        results[i] = desc.serialize(result)

    return results, {}
