__author__ = 'pezhang'

import os
import re
import math
import sys
from reserved_instance.parse_aws_info import AwsInfoTask
import splunk.Intersplunk as intersplunk
import splunk.search as search
import traceback
import utils.app_util as util

DAYS_OF_WEEK = 7
DAYS_OF_YEAR = 365
HOURS_OF_DAY = 24
# history data's first day and last day are not considered, so it should be 4 days
VALID_DAYS = 5
HOURS_OF_YEAR = DAYS_OF_YEAR * HOURS_OF_DAY
APP_LOOKUP_PATH = os.path.join(os.environ['SPLUNK_HOME'], 'etc', 'apps', 'splunk_app_aws', 'lookups')
PRICE_ON_DEMAND_HOURLY = 'on_demand_hourly'
PRICE_RESERVED_ONE_ALL_YEARLY = 'reserved_one_all_yearly'
PRICE_RESERVED_ONE_PARTIAL_YEARLY = 'reserved_one_partial_yearly'
PRICE_RESERVED_ONE_PARTIAL_HOURLY = 'reserved_one_partial_hourly'
PRICE_RESERVED_ONE_NO_HOURLY = 'reserved_one_no_hourly'
CURRENT_IH = 'current_ih'
RECOMMENDED_IH = 'recommended_ih'
CURRENT_DAY = 'current_d'
RECOMMENDED_DAY = 'recommended_d'
RI = 'ri'
RI_COST = 'ri_cost'
ON_DEMAND_COST = 'on_demand_cost'
MESSAGE = 'message'
CURRENCY = 'currency'

logger = util.get_logger()


def cal_ri(data, on_demand_hourly, reserved_hourly):
    sorted_data = sorted(data)
    k = int(reserved_hourly / on_demand_hourly * len(data))
    index = min(max(len(data) - k - 1, 0), len(data) - 1)
    return int(round(sorted_data[index]))


def cal_ri_cost(data, ri_count, on_demand_hourly, reserved_hourly):
    hours = 0
    for i in xrange(len(data)):
        if data[i] > ri_count:
            hours += data[i] - ri_count
    return hours * on_demand_hourly + ri_count * reserved_hourly * len(data)


# return recommended RI and corresponding RI cost
def ri_wrap(data, on_demand_hourly, reserved_hourly):
    if on_demand_hourly == 0:  # current region doesn't support specific reserved instance
        return 'N/A', 'N/A', 'This region may not support reserved instance for this type or price information is out-of-date.'

    ri = cal_ri(data, on_demand_hourly, reserved_hourly)
    ri_cost = cal_ri_cost(data, ri, on_demand_hourly, reserved_hourly)
    return ri, ri_cost, 'Details'

def _parse_search_result(value):
    if value is None:
        return 0
    else:
        return float(str(value))

def read_price(location, instance_type, product_os, tenancy, session_key):
    if tenancy == 'On Demand':
        tenancy = 'Shared'
    elif tenancy == 'Dedicated' or tenancy == 'Dedicated Usage':
        tenancy = 'Dedicated'

    pre_install = 'NA'
    # the format of product_os is "Windows with XXXX"
    if 'Windows' in product_os:
        if len(product_os) > 13:
            pre_install = product_os[13:]

        product_os = 'Windows'

    if re.match(r'cn-.*', location) == None:
        csv_file = 'price'
        currency = '$'
    else:
        csv_file = 'cn_price'
        currency = '\xc2\xa5'.decode('utf8')
    try:
        price_results = search.searchAll(
            '| inputlookup {0} where region="{1}" AND instance_type="{2}" AND os="{3}" AND pre_install="{4}" AND tenancy="{5}" '
            '| table on_demand_hourly reserved_one_all_yearly reserved_one_partial_yearly reserved_one_partial_hourly reserved_one_no_hourly'
                .format(csv_file, location, instance_type, product_os, pre_install, tenancy),
            sessionKey=session_key)
        if len(price_results) == 0:
            return 0, 0, 0, 0, 0, currency
        else:
            result_dict = {}
            # parse price search results
            for result in price_results:
                result_dict[PRICE_ON_DEMAND_HOURLY] = _parse_search_result(result.get(PRICE_ON_DEMAND_HOURLY))
                result_dict[PRICE_RESERVED_ONE_ALL_YEARLY] = _parse_search_result(result.get(PRICE_RESERVED_ONE_ALL_YEARLY))
                result_dict[PRICE_RESERVED_ONE_PARTIAL_YEARLY] = _parse_search_result(result.get(PRICE_RESERVED_ONE_PARTIAL_YEARLY))
                result_dict[PRICE_RESERVED_ONE_PARTIAL_HOURLY] = _parse_search_result(result.get(PRICE_RESERVED_ONE_PARTIAL_HOURLY))
                result_dict[PRICE_RESERVED_ONE_NO_HOURLY] = _parse_search_result(result.get(PRICE_RESERVED_ONE_NO_HOURLY))

            return result_dict[PRICE_ON_DEMAND_HOURLY], result_dict[PRICE_RESERVED_ONE_ALL_YEARLY], result_dict[PRICE_RESERVED_ONE_PARTIAL_YEARLY], \
                   result_dict[PRICE_RESERVED_ONE_PARTIAL_HOURLY], result_dict[PRICE_RESERVED_ONE_NO_HOURLY], currency
    except:
        return 0, 0, 0, 0, 0, currency


# get valid_days from conf
def get_valid_days_from_conf(session_key):
    valid_length = -1
    message = 'It\'s required to set ri_recommendation_minimum_sample_days in recommendation.conf'
    try:
        minimum_days = util.get_option_from_conf(session_key, 'recommendation', 'ec2',
                                                 'ri_recommendation_minimum_sample_days')
        if minimum_days is None:
            return valid_length, message
        else:
            minimum_days = int(float(minimum_days))
            if minimum_days < 0:
                return valid_length, 'It\'s required to set positive days in recommendation.conf'
            elif minimum_days < VALID_DAYS:
                return valid_length, 'In order to give reliable results, days should be bigger than %d in recommendation.conf' % (
                    VALID_DAYS)
            else:
                return max(minimum_days, VALID_DAYS), 'Details'
    except:
        return valid_length, message


def hours_weight_cmp(x, y):
    if x['diff'] != y['diff']:
        return -1 if x['diff'] > y['diff'] else 1
    else:
        if x['value'] == y['value']:
            return 0
        returnCoeff = -1
        if x['value'] > y['value']:
            bigger = x['value']
            smaller = y['value']
        else:
            returnCoeff = 1
            bigger = y['value']
            smaller = x['value']
        pro = smaller / bigger
        add_s_pro = math.floor(smaller + 1) / (1.0 if bigger < 1 else math.floor(bigger))
        add_b_pro = math.floor(smaller) / math.floor(bigger + 1)
        add_s_diff = abs(add_s_pro - pro)
        add_b_diff = abs(add_b_pro - pro)
        if add_s_diff == add_b_diff:
            return 0
        else:
            return returnCoeff * -1 if add_s_diff < add_b_diff else returnCoeff * 1

def distribute_day_according_hour(day, hour):
    if len(day) == 0 or len(hour) == 0 or len(day) != len(hour) / HOURS_OF_DAY:
        return []
    results = [0] * len(day) * HOURS_OF_DAY
    for i in xrange(len(day)):
        hours_sum = round(day[i])
        if hours_sum == 0:
            continue
        remained_hours = hours_sum
        hours_weight = []
        hours_distribution = hour[i * HOURS_OF_DAY: (i + 1) * HOURS_OF_DAY]
        distrbution_sum = sum(hours_distribution)
        hours_distribution = [hours_distribution[j] / distrbution_sum if distrbution_sum != 0 else 1.0 / HOURS_OF_DAY
                              for j in xrange(HOURS_OF_DAY)]
        for j in xrange(HOURS_OF_DAY):
            results_index = i * HOURS_OF_DAY + j
            results[results_index] = math.floor(hours_distribution[j] * hours_sum)
            hours_weight.append({'index': j, 'diff': hours_distribution[j] * hours_sum - results[results_index],
                                 'value': results[results_index]})
            remained_hours -= results[results_index]
        if remained_hours > 0:
            # still some hours not be distributed
            hours_weight = sorted(hours_weight, cmp=hours_weight_cmp)
            while remained_hours > 0 and len(hours_weight) > 0:
                results[i * HOURS_OF_DAY + hours_weight.pop(0)['index']] += 1
                remained_hours -= 1
    return results

# return actual instance hours, predicted instance hours of 1 year and corresponding time line list
def get_instance_hours(base, search_results):
    if len(search_results) == 0:
        return 0, []
    history_ih = [float(str(search_results[i][CURRENT_IH])) for i in xrange(0, len(search_results)) if
                  search_results[i][CURRENT_IH]]
    if base == 'history':
        return len(history_ih), history_ih
    else:
        predicted_ih = [max(float(str(search_results[i][RECOMMENDED_IH])), 0) for i in
                        xrange(len(search_results)) if not (search_results[i][CURRENT_IH])]
        predicted_day = [max(float(str(search_results[i][RECOMMENDED_DAY])), 0) for i in
                         xrange(len(search_results)) if
                         search_results[i][RECOMMENDED_DAY] and not (search_results[i][CURRENT_DAY])]
        results = distribute_day_according_hour(predicted_day, predicted_ih)
        return len(history_ih), results


def main():
    try:
        search_results, dummyresults, settings = intersplunk.getOrganizedResults()
        session_key = settings['sessionKey']
        if len(sys.argv) == 2:
            # update aws price info
            if sys.argv[1] == 'info':
                task = AwsInfoTask(session_key)
                task.execute()
        elif len(sys.argv) == 5:
            # obtain price detail
            region = sys.argv[1]
            instance_type = sys.argv[2]
            product_os = sys.argv[3]
            tenancy = sys.argv[4]
            on_demand_hourly, reserved_one_all_yearly, reserved_one_partial_yearly, reserved_one_partial_hourly, reserved_one_no_hourly, currency = read_price(
                region, instance_type, product_os, tenancy, session_key)

            intersplunk.outputResults([{PRICE_ON_DEMAND_HOURLY: on_demand_hourly,
                                        PRICE_RESERVED_ONE_ALL_YEARLY: reserved_one_all_yearly,
                                        PRICE_RESERVED_ONE_PARTIAL_YEARLY: reserved_one_partial_yearly,
                                        PRICE_RESERVED_ONE_PARTIAL_HOURLY: reserved_one_partial_hourly,
                                        PRICE_RESERVED_ONE_NO_HOURLY: reserved_one_no_hourly, CURRENCY: currency}],
                                      fields=[PRICE_ON_DEMAND_HOURLY, PRICE_RESERVED_ONE_ALL_YEARLY,
                                              PRICE_RESERVED_ONE_PARTIAL_YEARLY,
                                              PRICE_RESERVED_ONE_PARTIAL_HOURLY, PRICE_RESERVED_ONE_NO_HOURLY,
                                              CURRENCY])
        elif len(sys.argv) == 7:
            # calculate optimal RI, RI cost and on demand cost
            base = sys.argv[1]
            region = sys.argv[2]
            instance_type = sys.argv[3]
            purchase_option = sys.argv[4]
            product_os = sys.argv[5]
            tenancy = sys.argv[6]

            valid_days, message = get_valid_days_from_conf(session_key)
            if valid_days < 0:
                ri = 'N/A'
                ri_cost = 'N/A'
                instance_hours = []
                on_demand_hourly = 0
                currency = '$' if re.match(r'cn-.*', region) == None else '\xc2\xa5'.decode('utf8')
            else:
                history_len, instance_hours = get_instance_hours(base, search_results)
                # read price
                on_demand_hourly, reserved_one_all_yearly, reserved_one_partial_yearly, reserved_one_partial_hourly, reserved_one_no_hourly, currency = read_price(
                    region, instance_type, product_os, tenancy, session_key)

                if valid_days * HOURS_OF_DAY > history_len:
                    ri = 'N/A'
                    ri_cost = 'N/A'
                    message = 'It\'s required to have %d days\' data at least. You can update the setting in recommendation.conf' % (
                        valid_days)
                else:
                    if purchase_option == 'all':
                        ri, ri_cost, message = ri_wrap(instance_hours, on_demand_hourly,
                                                       reserved_one_all_yearly / HOURS_OF_YEAR)
                    elif purchase_option == 'partial':
                        ri, ri_cost, message = ri_wrap(instance_hours, on_demand_hourly,
                                                       reserved_one_partial_yearly / HOURS_OF_YEAR + reserved_one_partial_hourly)
                    else:
                        ri, ri_cost, message = ri_wrap(instance_hours, on_demand_hourly, reserved_one_no_hourly)

            instance_hours_len = max(1, len(instance_hours))
            outputResults = []
            cur_line = {}
            cur_line[ON_DEMAND_COST] = int(
                round(on_demand_hourly * sum(instance_hours) / instance_hours_len * HOURS_OF_YEAR))  # on demand cost
            cur_line[RI] = ri
            cur_line[RI_COST] = 'N/A' if ri_cost == 'N/A' else int(
                round(ri_cost / instance_hours_len * HOURS_OF_YEAR))  # RI cost
            cur_line[MESSAGE] = message
            cur_line[CURRENCY] = currency
            outputResults.append(cur_line)
            intersplunk.outputResults(outputResults,
                                      fields=[RI, RI_COST, ON_DEMAND_COST, MESSAGE, CURRENCY])
        else:
            intersplunk.parseError(
                "Arguments should be recommendation base, AZ, instance type, purchase option, os and tenancy.")
    except:
        stack = traceback.format_exc()
        results = intersplunk.generateErrorResults("Error : Traceback: " + str(stack))
        intersplunk.outputResults(results)


if __name__ == "__main__":
    main()
