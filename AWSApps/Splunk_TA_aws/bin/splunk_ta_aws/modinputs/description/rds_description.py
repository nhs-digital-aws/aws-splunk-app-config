import boto.rds

import splunksdc.log as logging
import splunk_ta_aws.common.ta_aws_consts as tac
import splunk_ta_aws.common.ta_aws_common as tacommon
import description as desc

logger = logging.get_module_logger()


def connect_rds_to_region(config):
    return desc.BotoRetryWrapper(boto_client=tacommon.connect_service_to_region(
        boto.rds.connect_to_region, config))


@desc.describe_pagination
@desc.refresh_credentials
def rds_instances(config, **kwargs):
    keys = ["DBName", "OptionGroupName", "PubliclyAccessible", "Status",
            "allocated_storage", "auto_minor_version_upgrade",
            "availability_zone", "backup_retention_period",
            "character_set_name", "create_time", "endpoint", "engine",
            "engine_version", "id", "instance_class", "iops",
            "latest_restorable_time", "license_model",
            "master_username", "multi_az", "parameter_groups",
            "pending_modified_values", "preferred_backup_window",
            "preferred_maintenance_window",
            "read_replica_dbinstance_identifiers", "status", "status_infos",
            "subnet_group", "vpc_security_groups"]
    pg_keys = ["name", "ParameterApplyStatus"]
    subnet_keys = ["description", "name", "status", "subnet_ids", "vpc_id"]
    vsg_keys = ["status", "vpc_group"]
    # FIXME security_groups, pagination
    # https://github.com/boto/boto/issues/3109

    conn = connect_rds_to_region(config)
    instances = conn.get_all_dbinstances(**kwargs)
    pagination = {'marker': instances.next_marker}

    region = {"region": config[tac.region],
              tac.account_id: config[tac.account_id]}
    results = desc.pop_description_results(
        instances, keys, region, pop_region_name=False, raw_event=True)
    for i, result in enumerate(results):
        result["parameter_groups"] = desc.pop_description_results(
            result["parameter_groups"], pg_keys, {},
            pop_region_name=False, raw_event=True)
        result["subnet_group"] = desc.pop_description_result(
            result["subnet_group"], subnet_keys, {},
            pop_region_name=False, raw_event=True)
        result["vpc_security_groups"] = desc.pop_description_results(
            result["vpc_security_groups"], vsg_keys, {},
            pop_region_name=False, raw_event=True)
        results[i] = desc.serialize(result)
    return results, pagination
