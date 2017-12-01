__author__ = 'pezhang'
import splunk.Intersplunk as intersplunk
import traceback

OUTPUT_COUNT = 100
OUTPUT_ATTRIBUTE_FIELDS = ['_time', 'job_name', 'info_min_time', 'info_max_time']

def comparator(s):
    return -1 * s['_time']

def parse_table(input):
    output = []
    for i in xrange(len(input)):
        if len(output) == OUTPUT_COUNT:
            break

        fields = input[i].keys()
        value_fields = list(filter(lambda x: x.startswith('value_'), fields))
        for value_field in value_fields:
            cur_field = value_field[6:]
            outlier_field = 'outlier_' + cur_field
            severity_field = 'severity_' + cur_field
            if outlier_field in search_results[i] and str(search_results[i][outlier_field]) == 'True':
                if len(str(search_results[i][severity_field])) > 0:
                    severity_value = search_results[i][severity_field]
                else:
                    severity_value = -1
                cur_row = {'Field name': cur_field, 'Value': input[i][value_field], 'Severity': severity_value}
                cur_row.update({k: input[i][k] for k in OUTPUT_ATTRIBUTE_FIELDS if k in input[i]})
                output.append(cur_row)

    sorted(output, key=comparator)
    return output


try:
    output_fields = ['_time', 'Job name', 'Field name', 'Value', 'Severity']
    output_results = []
    search_results, dummyresults, settings = intersplunk.getOrganizedResults()
    if search_results is None or len(search_results) == 0:
        intersplunk.outputResults(output_results)

    output_results = parse_table(search_results)
    intersplunk.outputResults(output_results[:OUTPUT_COUNT], fields=OUTPUT_ATTRIBUTE_FIELDS.extend(['Field name', 'Value', 'Severity']))
except:
    stack = traceback.format_exc()
    results = intersplunk.generateErrorResults("Error : Traceback: " + str(stack))
    intersplunk.outputResults(results)
