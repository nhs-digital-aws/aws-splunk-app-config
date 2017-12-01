import uuid
import re
import json

import splunksdc.log as logging
from splunktaucclib.rest_handler.error import RestError

logger = logging.get_module_logger()

CONFLICT_FIELD = '_conflict_fields'
IGNORED_CONFLICT_FIELDS = [CONFLICT_FIELD]

ALLOW_EMPTY = ['rule_names']

def _extract_name(name):
    """Extract the user-input name from a full name.

    For example, if the user-input name is "myname", then the full name should be "myname_[uuid]". This function will
    take "myname_[uuid]" as input and "myname" as output.

    If the full name does not match this pattern, it will return the full name directly.


    Args:
        name (string): The stanza name. For example "myname_[uuid]"

    Returns:
        string: The user-input name or full name. Return "myname" in the previous case.
    """
    splitted = re.split(r"_[0-9A-F]{8}-[0-9A-F]{4}-[4][0-9A-F]{3}-[89AB][0-9A-F]{3}-[0-9A-F]{12}$", name, 0, re.I)
    if len(splitted) == 2:
        return splitted[0]
    else:
        return name


def _build_name(origin_name):
    """Build the stanza name based on the user-input name.

    Args:
        origin_name (string): The user-input name, e.g. "myname"

    Returns:
        string: The full name, e.g. "myname_[uuid]"
    """
    return origin_name + '_' + str(uuid.uuid4())


def merge_inputs(input_name, inputs, fields):
    """Merge the inputs based on the user-input name.

    All inputs with the same user-input name will be merged into one input.
    "myname_[uuid1]", "myname_[uuid2]", "myname_[uuid3]", "myname2_[uuid]" will be merged into "myname", "myname2".
    All fields in `fields` will be dumped. All other common fields will be keeped since they should be all the same.

    TODO: If there is any confliction in common fields, an error will be throw.

    Args:
        input_name (string): The name of input (aws_cloudwatch and etc.)
        inputs (string): Raw inputs fetched from the original inputs collection.
        fields (list): Fields that will be merged.

    Returns:
        dict: The dict of merged inputs. The key is the input name (user-input name) while the
    """
    input_dict = dict()

    for i in inputs:
        logger.debug(i.content)
        new_name = _extract_name(i.name)

        if new_name in input_dict:
            item = input_dict[new_name]

            # Iterate over all keys to merge fields and check conflict
            for key in item:
                value = i.content.get(key, '')

                # For merged fields, merge the value
                if key in fields:
                    item[key].append(value)

                # For other fields, check whether there is any conflict
                else:
                    if (key not in IGNORED_CONFLICT_FIELDS) and (item[key] != value):
                        logger.warn('There is conflict in input %s, field %s, values (%s) vs (%s)' % (new_name, key, item[key], value))
                        if key not in item[CONFLICT_FIELD]:
                            item[CONFLICT_FIELD][key] = set([item[key], value])
                        else:
                            item[CONFLICT_FIELD][key].add(value)


        # Set the first input as base
        else:
            input_dict[new_name] = copy_content(input_name, i)
            input_dict[new_name][CONFLICT_FIELD] = dict()
            for key in fields:
                input_dict[new_name][key] = [i.content.get(key, '')]

    for i in input_dict:
        if CONFLICT_FIELD in input_dict[i]:
            for f in input_dict[i][CONFLICT_FIELD]:
                input_dict[i][CONFLICT_FIELD][f] = list(input_dict[i][CONFLICT_FIELD][f])

    return input_dict


def separate_inputs(name, origin_input, fields):
    """Separate group input into stanzas.

    If there are multiple values in `fields`, then they will be separated into multiple inputs.
    All other fields will be remains the same.

    In some cases, for example, the user clicks "disable" in UI, only `{disabled: 1}` will be sent and there is no
    group fields.

    Args:
        name (string): The user-input name
        origin_input (dict): The original input posted by the frontend
        fields (list): Fields that will be separated.

    Returns:
        dict: Dict of separated inputs.
    """
    group_count = -1
    for f in fields:
        # In case of `{disabled: 1}`, there is no group fields.
        if f not in origin_input:
            continue

        try:
            origin_input[f] = json.loads(origin_input[f])
        except:
            raise RestError(
                400,
                origin_input[f]
            )

        # Make sure every fields in group input have the same number of items.
        if group_count == -1:
            group_count = len(origin_input[f])
        else:
            if group_count != len(origin_input[f]):
                logger.error('Group input fields does not match')
                raise RestError(
                    400,
                    'Group input fields does not match'
                )

        # Check if there is any empty value. Any empty field will be an empty string (not None).
        if f in ALLOW_EMPTY:
            continue

        if '' in origin_input[f]:
            logger.error('Field %s cannot be empty' % f)
            raise RestError(
                400,
                'Field %s cannot be empty' % f
            )


    inputs_dict = dict()
    inputs_set = set()
    for i in range(group_count):
        separated_input = dict()
        group_fields = dict()

        for k in origin_input:
            if k in fields:
                separated_input[k] = origin_input[k][i]
                group_fields[k] = origin_input[k][i]
            else:
                separated_input[k] = origin_input[k]

        input_str = str(group_fields)

        if input_str in inputs_set:
            raise RestError(
                400,
                'Duplicated input %s' % input_str
            )

        inputs_set.add(input_str)
        inputs_dict[_build_name(name)] = separated_input

    if len(inputs_dict) > 0:
        logger.info('%d inputs are generated.' % (len(inputs_dict)))
    else:
        inputs_dict = {
            'unknown': origin_input
        }
        logger.info('No input is generated based on group fields. Wrap the original '
                    'one as an special input %s to keep the output consistent' % str(inputs_dict))

    return inputs_dict


def match_inputs(input_name, inputs, name):
    """ Filter the inputs based on the user-input name

    Args:
        input_name (string): The name of input (aws_cloudwatch and etc.)

        inputs (list): The original inputs in the list of entities

        name (string): The user-input name

    Returns:
        dict: The matched inputs.
    """
    input_dict = dict()

    inputs = filter(lambda i: _extract_name(i.name) == name, inputs)

    for i in inputs:
        input_dict[i.name] = copy_content(input_name, i)

    return input_dict


""" Copy the content of a stanza to a dict

    Args:
        input_name (string): The name of input (aws_cloudwatch and etc.)

        input_stanza (object): The stanza get from rest

    Returns:
        dict: The content of the stanza
    """
def copy_content(input_name, input_stanza):
    input_dict = input_stanza.content.copy()
    if input_name == 'aws_cloudwatch':
        input_dict.pop('interval', None)

    return input_dict
