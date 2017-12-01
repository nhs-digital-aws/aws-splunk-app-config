__author__ = 'pezhang'

import utils.app_util as util
import csv
import json
import os
import requests
import tempfile

APP_LOOKUP_PATH = os.path.join(os.environ['SPLUNK_HOME'], 'etc', 'apps', 'splunk_app_aws', 'lookups')
DOWNLOAD_URL = 'https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/index.json'
DOWNLOAD_FILE_NAME = 'splunk_aws_ec2_index.json'
PRODUCT = 'products'
PRODUCT_ATTRI = 'attributes'
PRODUCT_INSTANCE_TYPE = 'instanceType'
PRODUCT_OS = 'operatingSystem'
PRODUCT_LOC = 'location'
PRODUCT_TENANCY = 'tenancy'
PRODUCT_PREINSTALL = 'preInstalledSw'
PRICE_INFO = 'terms'
PRICE_ON_DEMAND = 'OnDemand'
PRICE_RESERVED = 'Reserved'
PRICE_ATTRI = 'termAttributes'
PRICE_DIMENSION = 'priceDimensions'
PRICE_UNIT_DIMENSION = 'pricePerUnit'
PRICE_ON_DEMAND_HOURLY = 'on_demand_hourly'
PRICE_RESERVED_ONE_ALL_YEARLY = 'reserved_one_all_yearly'
PRICE_RESERVED_ONE_PARTIAL_YEARLY = 'reserved_one_partial_yearly'
PRICE_RESERVED_ONE_PARTIAL_HOURLY = 'reserved_one_partial_hourly'
PRICE_RESERVED_ONE_NO_HOURLY = 'reserved_one_no_hourly'
PRICE_UNIT = 'USD'
ALL_UPFRONT_OPTION = 'A'
PARTIAL_UPFRONT_OPTION = 'P'
NO_UPFRONT_OPTION = 'N'

def location_to_region():
    filename = os.path.join(APP_LOOKUP_PATH, 'regions.csv')
    region_dict = dict()
    try:
        with open(filename, 'r') as file:
            reader = csv.reader(file)
            for line in reader:
                region_dict[line[4]] = line[0]
        return region_dict
    except:
        return region_dict


# download price.json from URL provided by AWS
def download_AWS_json():
    try:
        info = requests.get(DOWNLOAD_URL)
    except:
        return False
    filepath = os.path.join(tempfile.gettempdir(), DOWNLOAD_FILE_NAME)
    try:
        with open(filepath, 'w') as info_file:
            info_file.write(info.content)
            return True
    except:
        return False

def _build_set(attrs):
    return '|'.join([attrs[PRODUCT_LOC], attrs[PRODUCT_OS], attrs[PRODUCT_TENANCY], attrs[PRODUCT_PREINSTALL], attrs[PRODUCT_INSTANCE_TYPE]])

# obtain price info from downloaded json file
def parse_price(session_key):
    filepath = os.path.join(tempfile.gettempdir(), DOWNLOAD_FILE_NAME)
    with open(filepath, 'r') as index_file:
        price = dict()
        index = json.load(index_file)
        products = index[PRODUCT]
        on_demand = index[PRICE_INFO][PRICE_ON_DEMAND]
        reserved = index[PRICE_INFO][PRICE_RESERVED]
        for product_key in products.keys():
            product_attributes = products[product_key][PRODUCT_ATTRI]
            if PRODUCT_INSTANCE_TYPE not in product_attributes or PRODUCT_OS not in product_attributes or \
                            PRODUCT_OS not in product_attributes or PRODUCT_TENANCY not in product_attributes or \
                            PRODUCT_PREINSTALL not in product_attributes or PRODUCT_LOC not in product_attributes or \
                            'ebsOptimized' in product_attributes:
                continue

            if product_key not in on_demand or product_key not in reserved:
                continue

            set_name = _build_set(product_attributes)
            if set_name in price:
                continue

            on_demand_infos = on_demand[product_key].values()
            on_demand_hour = float(
            on_demand_infos[0][PRICE_DIMENSION].values()[0][PRICE_UNIT_DIMENSION][PRICE_UNIT])

            for reserved_info in reserved[product_key].values():
                contract_length = int(reserved_info[PRICE_ATTRI]['LeaseContractLength'][0:1])
                purchase_option = reserved_info[PRICE_ATTRI]['PurchaseOption'][0:1]
                if contract_length != 1:  # only consider one year
                    continue

                price_dimensions = reserved_info[PRICE_DIMENSION]
                if purchase_option == ALL_UPFRONT_OPTION:
                    for price_dimension in price_dimensions.values():
                        if price_dimension['unit'] == 'Quantity':
                            one_all_upfront_year = float(price_dimension[PRICE_UNIT_DIMENSION][PRICE_UNIT])
                elif purchase_option == PARTIAL_UPFRONT_OPTION:
                    for price_dimension in price_dimensions.values():
                        if price_dimension['unit'] == 'Quantity':
                            one_partial_upfront_year = float(price_dimension[PRICE_UNIT_DIMENSION][PRICE_UNIT])
                        else:
                            one_partial_upfront_hour = float(price_dimension[PRICE_UNIT_DIMENSION][PRICE_UNIT])
                else:
                    for price_dimension in price_dimensions.values():
                        if price_dimension['unit'] != 'Quantity':
                            one_no_upfront_hour = float(price_dimension[PRICE_UNIT_DIMENSION][PRICE_UNIT])


            price[set_name] = dict()
            price[set_name][PRICE_ON_DEMAND_HOURLY] = on_demand_hour
            price[set_name][PRICE_RESERVED_ONE_ALL_YEARLY] = one_all_upfront_year
            price[set_name][PRICE_RESERVED_ONE_PARTIAL_YEARLY] = one_partial_upfront_year
            price[set_name][PRICE_RESERVED_ONE_PARTIAL_HOURLY] = one_partial_upfront_hour
            price[set_name][PRICE_RESERVED_ONE_NO_HOURLY] = one_no_upfront_hour

    header = ['instance_type', 'region', 'os', 'tenancy', 'pre_install', PRICE_ON_DEMAND_HOURLY, PRICE_RESERVED_ONE_ALL_YEARLY,
              PRICE_RESERVED_ONE_PARTIAL_YEARLY, PRICE_RESERVED_ONE_PARTIAL_HOURLY,
              PRICE_RESERVED_ONE_NO_HOURLY]
    content = []
    region_dict = location_to_region()
    for set_name in price.keys():
        [location, product_os, tenancy, pre_install, instance_type] = set_name.split('|')
        if str(location) not in region_dict:
            continue

        content.append({'instance_type': instance_type, 'region': region_dict[str(location)],
                        'os': product_os, 'tenancy': tenancy, 'pre_install': pre_install,
                        PRICE_ON_DEMAND_HOURLY: price[set_name][PRICE_ON_DEMAND_HOURLY],
                        PRICE_RESERVED_ONE_ALL_YEARLY: price[set_name][
                            PRICE_RESERVED_ONE_ALL_YEARLY],
                        PRICE_RESERVED_ONE_PARTIAL_YEARLY: price[set_name][
                            PRICE_RESERVED_ONE_PARTIAL_YEARLY],
                        PRICE_RESERVED_ONE_PARTIAL_HOURLY: price[set_name][
                            PRICE_RESERVED_ONE_PARTIAL_HOURLY],
                        PRICE_RESERVED_ONE_NO_HOURLY: price[set_name][
                            PRICE_RESERVED_ONE_NO_HOURLY]
                        })

    util.update_lookup_file(session_key, 'price.csv', header, content)


class AwsInfoTask():
    def __init__(self, session_key):
        self.session_key = session_key

    def execute(self):
        if download_AWS_json():
            parse_price(self.session_key)

