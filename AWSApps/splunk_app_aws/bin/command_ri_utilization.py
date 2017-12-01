__author__ = 'pezhang'

import reserved_instance.reserved_instance_const as const
from reserved_instance.reserved_instance_utilization_calculator import RIUtilizationCalculator
import splunk.Intersplunk as intersplunk
import traceback
import utils.app_util as util

TENANCY = 'tenancy'
PLATFORM = 'platform'
RI_INFO = 'RI_info'
INSTANCE_INFO = 'run_instance_info'
TOTAL_HOURS = 'total_hours'
DELETE_KEYS = [INSTANCE_INFO, RI_INFO, TOTAL_HOURS]


logger = util.get_logger()


def cal_utilization(search_results):
    output_results = []
    for line in search_results:
        total_hours = float(line[TOTAL_HOURS])
        tenancy = line[TENANCY]
        platform = line[PLATFORM]
        
        calculator = RIUtilizationCalculator(total_hours, line[RI_INFO], line[INSTANCE_INFO], platform, tenancy)
        calculator.cal_utilization()
        results = calculator.get_results()

        line.update(results)
        for key in DELETE_KEYS:
            if key in line:
                del line[key]
        output_results.append(line)

    return output_results

def main():
    try:
        search_results, dummy_results, settings = intersplunk.getOrganizedResults()
        if len(search_results) > 0:
            output_results = cal_utilization(search_results)
            intersplunk.outputResults(output_results, fields=output_results[0].keys())
    except:
        stack = traceback.format_exc()
        results = intersplunk.generateErrorResults("Error : Traceback: " + str(stack))
        intersplunk.outputResults(results)


if __name__ == "__main__":
    main()
