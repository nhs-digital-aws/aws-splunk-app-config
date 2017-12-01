import boto.ec2
import boto3

import splunksdc.log as logging
import splunk_ta_aws.common.ta_aws_consts as tac
import splunk_ta_aws.common.ta_aws_common as tacommon
import description as desc


logger = logging.get_module_logger()


EC2_IMAGE_KEYS = ["id", "location", "state", "owner_id", "owner_alias",
        "is_public", "architecture", "platform", "type", "kernel_id",
        "ramdisk_id", "name", "description", "product_codes",
        "billing_products", "root_device_type", "root_device_name",
        "virtualization_type", "hypervisor", "instance_lifecycle",
        "sriov_net_support"]


def connect_ec2_to_region(config):
    return desc.BotoRetryWrapper(boto_client=tacommon.connect_service_to_region(
        boto.ec2.connect_to_region, config))


@desc.describe_pagination
@desc.refresh_credentials
def ec2_instances(config, **kwargs):
    keys = ["state", "state_code", "previous_state", "previous_state_code",
            "placement", "placement_group", "placement_tenancy",
            "ami_launch_index", "architecture", "client_token", "dns_name",
            "ebs_optimized", "group_name", "hypervisor", "id", "image_id",
            "instance_profile", "instance_type", "ip_address", "item",
            "kernel", "key_name", "launch_time", "monitored", "monitoring",
            "monitoring_state", "persistent", "platform", "private_dns_name",
            "private_ip_address", "public_dns_name", "reason",
            "root_device_name", "root_device_type", "sourceDestCheck",
            "spot_instance_request_id", "subnet_id", "tags",
            "virtualization_type", "vpc_id"]

    ec2_conn = connect_ec2_to_region(config)
    reservations = ec2_conn.get_all_reservations(**kwargs)
    pagination = {'next_token': reservations.next_token}

    results = []
    image_cache_map = {}

    for reservation in reservations:
        instances = reservation.instances

        # describe ec2 image
        for instance in instances:
            image = {}
            image_id = getattr(instance, 'image_id', None)
            if image_id is not None:

                if image_id not in image_cache_map:
                    image_attributes = ec2_conn.get_image(image_id)
                    image_cache_map[image_id] = image_attributes
                else:
                    image_attributes = image_cache_map[image_id]

                # image_attributes will be None if the corresponding EC2 image does not exist anymore
                if image_attributes is not None:
                    image = desc.pop_description_result(image_attributes, EC2_IMAGE_KEYS, {}, raw_event=True)

            result = desc.pop_description_result(instance, keys, {
                "owner_id": reservation.owner_id,
                tac.account_id: config[tac.account_id],
                "image": {
                    "id": image_id,
                    "attributes": image
                }
            })

            results.append(result)

    return results, pagination


@desc.describe_pagination  # No pagination
@desc.refresh_credentials
def ec2_reserved_instances(config):
    ec2_client = desc.BotoRetryWrapper(boto_client=boto3.client(
        'ec2',
        region_name=config.get(tac.region),
        aws_access_key_id=config.get(tac.key_id),
        aws_secret_access_key=config.get(tac.secret_key),
        aws_session_token=config.get('aws_session_token')
    ))

    keys = ['ReservedInstancesId', 'OfferingType', 'InstanceCount', 'AvailabilityZone', 'InstanceType', 'InstanceTenancy', 'State',
            'FixedPrice', 'ProductDescription', 'UsagePrice', 'CurrencyCode', 'Start', 'End', 'Duration', 'Scope']

    reserved_instances = ec2_client.describe_reserved_instances()['ReservedInstances']
    results = desc.pop_description_results(reserved_instances, keys, {tac.account_id: config[tac.account_id], tac.region: config[tac.region]}, pop_region_name=False)

    return results, {}


# TODO: boto3 supports pagination
@desc.describe_pagination
@desc.refresh_credentials
def ec2_ebs_snapshots(config):
    keys = ["description", "encrypted", "id", "item", "owner_alias",
            "owner_id", "progress", "start_time", "status", "tags",
            "volume_id", "volume_size"]

    ec2_conn = connect_ec2_to_region(config)

    snapshots = ec2_conn.get_all_snapshots(owner="self")

    results = desc.pop_description_results(
        snapshots, keys, {tac.account_id: config[tac.account_id]})

    return results, {}


# TODO: boto3 supports pagination
@desc.describe_pagination
@desc.refresh_credentials
def ec2_volumes(config):
    vol_keys = ["attach_data", "encrypted", "type", "id", "status",
                "snapshot_id", "size", "iops", "tags", "create_time", "zone"]
    attach_keys = ["attach_time", "deleteOnTermination", "device", "id",
                   "instance_id", "status"]

    ec2_conn = connect_ec2_to_region(config)
    volumes = ec2_conn.get_all_volumes()

    results = desc.pop_description_results(
        volumes, vol_keys,  {tac.account_id: config[tac.account_id]},
        raw_event=True)
    for i, result in enumerate(results):
        attach = desc.pop_description_result(
            result["attach_data"], attach_keys, {},
            pop_region_name=False, raw_event=True)
        result["attach_data"] = attach
        results[i] = desc.serialize(result)
    return results, {}


@desc.describe_pagination  # No pagination
@desc.refresh_credentials
def ec2_security_groups(config):
    cg_keys = ["description", "id", "instances", "name", "owner_id",
               "rules_egress", "rules", "tags", "vpc_id"]

    ec2_conn = connect_ec2_to_region(config)
    cgs = ec2_conn.get_all_security_groups()

    results = desc.pop_description_results(
        cgs, cg_keys, {tac.account_id: config[tac.account_id]}, raw_event=True)

    for i, result in enumerate(results):
        result["rules_egress"] = _pop_rules(result["rules_egress"])
        result["rules"] = _pop_rules(result["rules"])
        instances = desc.pop_description_results(
            result["instances"](), ["id"], {}, pop_region_name=False,
            raw_event=True)
        result["instances"] = instances
        results[i] = desc.serialize(result)

    return results, {}


def _pop_rules(rules):
    rule_keys = ["from_port", "grants", "groups", "ipRanges",
                 "ip_protocol", "to_port"]
    grant_keys = ["cidr_ip", "group_id", "name", "owner_id"]

    rule_results = desc.pop_description_results(
        rules, rule_keys, {}, pop_region_name=False, raw_event=True)
    for rule in rule_results:
        rule["grants"] = desc.pop_description_results(
            rule["grants"], grant_keys, {}, pop_region_name=False,
            raw_event=True)
    return rule_results


@desc.describe_pagination  # No pagination
@desc.refresh_credentials
def ec2_key_pairs(config):
    keys = ["name", "fingerprint"]

    ec2_conn = connect_ec2_to_region(config)
    key_pairs = ec2_conn.get_all_key_pairs()

    results = desc.pop_description_results(
        key_pairs, keys, {tac.account_id: config[tac.account_id]})
    return results, {}


@desc.describe_pagination  # No pagination
@desc.refresh_credentials
def ec2_images(config):
    ec2_conn = connect_ec2_to_region(config)

    images = ec2_conn.get_all_images(owners='self')

    results = desc.pop_description_results(
        images, EC2_IMAGE_KEYS, {tac.account_id: config[tac.account_id]})

    return results, {}


@desc.describe_pagination  # No pagination
@desc.refresh_credentials
def ec2_addresses(config):
    keys = ["public_ip", "instance_id", "domain",
            "allocation_id", "association_id", "network_interface_id",
            "network_interface_owner_id", "private_ip_address"]

    ec2_conn = connect_ec2_to_region(config)

    addresses = ec2_conn.get_all_addresses()

    results = desc.pop_description_results(
        addresses, keys, {tac.account_id: config[tac.account_id]})

    return results, {}
