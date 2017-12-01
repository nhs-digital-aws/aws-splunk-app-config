__author__ = 'peter'

import re
from collections import OrderedDict
import splunk.entity as en
import splunk.Intersplunk as intersplunk

# all supported input types
aws_source_type_patten = 'aws:.*'
aws_input_location_pattern = '/data/inputs/aws_.*'

# get data volume per sourcetype
results, dummy_results, settings = intersplunk.getOrganizedResults()

# get all source types used in inputs
# TODO should get inputs from remote target if configured, not localhost
# This bug is not very critical because we have already calculated all sourcetypes start with "aws:"
all_inputs = en.getEntitiesList('data/inputs/all',
                                namespace=settings['namespace'],
                                owner=settings['owner'],
                                sessionKey=settings['sessionKey'])

# add more customized sourcetypes
source_types = set([x.get('sourcetype') for x in all_inputs if re.match(aws_input_location_pattern, x.get('eai:location')) is not None])

# get data volume per sourcetype
output = [x for x in results if x.get('series') in source_types or re.match(aws_source_type_patten, x.get('series')) is not None]

# return result
intersplunk.outputResults(output)
