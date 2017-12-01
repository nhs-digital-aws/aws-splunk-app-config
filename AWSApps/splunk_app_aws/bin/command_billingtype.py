# This custom command is used for removeing duplicate billing events.
import sys
import splunk.Intersplunk
import string

results = splunk.Intersplunk.readResults(None, None, True)

consolidated_sources = set()

for result in results:
    if 'RecordType' in result and result['RecordType'] == 'AccountTotal':
        consolidated_sources.add(result['source'])

for result in results:
    if 'RecordType' in result and result['RecordType'] == 'StatementTotal' and result['source'] in consolidated_sources:
        results.remove(result)
    
splunk.Intersplunk.outputResults(results)