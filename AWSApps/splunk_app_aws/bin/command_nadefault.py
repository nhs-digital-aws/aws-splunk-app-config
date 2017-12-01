import sys
import splunk.Intersplunk
import string

if len(sys.argv) < 2:
    splunk.Intersplunk.parseError("No arguments provided")

result_keys = []

i = 1
while i < len(sys.argv):
    result_keys.append(sys.argv[i])
    i += 1

results = splunk.Intersplunk.readResults(None, None, True)

if len(results) == 0:
    result_dict = {}
    for result_key in result_keys:
        result_dict[result_key] = 0

    results = [result_dict]
elif len(results) == 1:
    for result_key in result_keys:
        if result_key in results[0]:
            if not results[0][result_key]:
               results[0][result_key] = 0
        else:
            results[0][result_key] = 0
    
splunk.Intersplunk.outputResults(results)