__author__ = 'pezhang'

from datetime import datetime
import splunk.Intersplunk as intersplunk
import traceback


def preprocess(data, time, results_length, output_results, cur_field):
    """Fillnull cloudwatch billing.
    1. insert arithmetic sequence for null value.
    2. generate daily cost by subtracting last day's cost

    Args:
        data: detected field's data.
        time: detected field's time.
        results_length: range(len(data)).
        output_results: list to store preprocess result.
        cur_field: field name of data.
    Returns:
        boolean: check validation of data.
    """
    if results_length is None:
        return False

    if len(results_length) != len(data):
        return False

    not_null_index = []  # store not null value index
    not_null_list = [False if data[i] == '' else True for i in results_length]
    parsed_data = [0 if data[i] == '' else round(float(data[i]), 2) for i in results_length]

    for i in results_length:
        if not_null_list[i]:
            not_null_index.append(i)

    if len(not_null_index) == 0:
        return False

    not_null_index.insert(0, 0)

    if len(parsed_data) - 1 not in not_null_index:
        # if last one is null
        not_null_list_last_time = datetime.fromtimestamp(time[not_null_index[len(not_null_index) - 1]])
        last_one_time = datetime.fromtimestamp(time[len(parsed_data) - 1])
        if not_null_list_last_time.year == last_one_time.year and not_null_list_last_time.month == last_one_time.month:
            parsed_data[len(parsed_data) - 1] = parsed_data[not_null_index[len(not_null_index) - 1]]
            not_null_index.append(len(parsed_data) - 1)

    for i in xrange(len(not_null_index) - 1, 0, -1):
        start_index = not_null_index[i - 1]
        end_index = not_null_index[i]
        start_index_time = datetime.fromtimestamp(time[start_index])
        end_index_time = datetime.fromtimestamp(time[end_index])
        if start_index_time.year != end_index_time.year or start_index_time.month != end_index_time.month:
            # has 1st in current interval
            insert_value = parsed_data[start_index]
            while start_index_time.month != end_index_time.month:
                # from start to the day before end index' 1st, insert with start value
                parsed_data[start_index] = insert_value
                start_index += 1
                start_index_time = datetime.fromtimestamp(time[start_index])

        if start_index != end_index:
            # from start to end, insert with arithmetic sequence
            interval_value = (parsed_data[end_index] - parsed_data[start_index]) / float(end_index - start_index)
            for j in xrange(1, end_index - start_index + 1):
                parsed_data[j + start_index] = interval_value * j + parsed_data[start_index]

    for i in range(len(parsed_data) - 1, -1, -1):
        cur_time = datetime.fromtimestamp(time[i])
        if cur_time.day != 1 and i > 0:  # only 1st of month value doesn't need to substract last day's value
            parsed_data[i] = max(parsed_data[i] - parsed_data[i - 1], 0)
        output_results[i][cur_field] = round(parsed_data[i], 2)
    return True

def main():
    try:
        search_results, dummyresults, settings = intersplunk.getOrganizedResults()
        output_fields = ['_time', '_span']
        output_results = []
        if search_results is None or len(search_results) == 0:
            intersplunk.outputResults(output_results, fields=output_fields)
        else:
            fields = search_results[0].keys()
            detected_fields = list(filter(lambda x: x != '_time' and x != '_span', fields))
            search_results_length = range(len(search_results))
            timestamp = [int(str(search_results[i]['_time'])) for i in search_results_length]
            output_results = [{'_time': timestamp[i], '_span': search_results[i]['_span']} for i in search_results_length]
            for cur_field in detected_fields:
                data = [str(search_results[i][cur_field]) for i in search_results_length]
                if preprocess(data, timestamp, search_results_length, output_results, cur_field):
                    output_fields.append(cur_field)

            intersplunk.outputResults(output_results, fields=output_fields)
    except:
        stack = traceback.format_exc()
        results = intersplunk.generateErrorResults("Error : Traceback: " + str(stack))
        intersplunk.outputResults(results)

if __name__ == "__main__":
    main()
