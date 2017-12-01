__author__ = 'pezhang'

from anomaly_detection.algorithm.zscore import ZScore
import anomaly_detection.anomaly_detection_const as const
import splunk.Intersplunk as intersplunk
import traceback

algorithm = ZScore('l')


def check_fields(fields):
    detected_fields = list(filter(lambda x: x not in const.FILTER_FIELDS, fields))
    is_detection_needed = True
    for detected_field in detected_fields:
        if detected_field.startswith('severity_') or detected_field.startswith('outlier_') or detected_field.startswith(
                'value_'):
            is_detection_needed = False
            break
    is_field_valid = True
    try:
        fields.index('_time')
        if is_detection_needed:
            fields.index('_span')
    except ValueError:
        is_field_valid = False
    return is_field_valid, is_detection_needed


def wrap_anomaly_detection(search_results):
    fields = search_results[0].keys()
    detected_fields = list(filter(lambda x: x not in const.FILTER_FIELDS, fields))
    output_count = len(search_results) - algorithm.get_train_count()
    output_results = [{'_time': search_results[i + algorithm.get_train_count()]['_time']} for i in
                      xrange(output_count)]  # initialize output
    output_fields = ['_time']
    outlier_count = 0
    for cur_field in detected_fields:
        output_fields += ['value_' + cur_field, 'outlier_' + cur_field, 'severity_' + cur_field]
        try:
            cur_data = [float(str(search_results[i][cur_field])) for i in xrange(len(search_results))]
            outlier_indexes, severity_array = algorithm.anomaly_detection(cur_data)
            severity_index = 0
            outlier_count += len(outlier_indexes)
            for i in xrange(output_count):
                search_results_index = i + algorithm.get_train_count()

                output_results[i]['value_' + cur_field] = search_results[search_results_index][cur_field]
                output_results[i]['outlier_' + cur_field] = search_results_index in outlier_indexes
                output_results[i]['severity_' + cur_field] = severity_array[
                    severity_index] if search_results_index in outlier_indexes else 0

                if search_results_index in outlier_indexes:
                    severity_index += 1

        except ValueError:
            intersplunk.parseError('This command only supports numbers. Field %s is not numerical. ' % cur_field)

    if outlier_count == 0:
        return [], output_fields
    else:
        return output_results, output_fields


def main():
    try:
        output_fields = ['_time']
        output_results = []
        search_results, dummyresults, settings = intersplunk.getOrganizedResults()
        if search_results is None or len(search_results) == 0:
            intersplunk.outputResults(output_results, fields=output_fields)
            return

        fields = search_results[0].keys()
        is_field_valid, is_detection_needed = check_fields(fields)
        if not is_field_valid:
            intersplunk.parseError(
                'This visualization requires timestamped, evenly spaced numeric time-series data. Try using the timechart command in your query.')

        if not is_detection_needed:
            intersplunk.outputResults(search_results, fields=search_results[0].keys())
            return

        output_results, output_fields = wrap_anomaly_detection(search_results)
        intersplunk.outputResults(output_results, fields=output_fields)
    except:
        stack = traceback.format_exc()
        results = intersplunk.generateErrorResults("Error : Traceback: " + str(stack))
        intersplunk.outputResults(results)


if __name__ == "__main__":
    main()
