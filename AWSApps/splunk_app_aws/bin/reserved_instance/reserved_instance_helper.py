__author__ = 'pezhang'

def accumulate_to_dict(dict, keys, value):
    """
        Initialize hierarchical dict with giving keys and value.
        If dict has giving keys, add value to dict's existing value.
        Keys could be a string like "a.b.c" or a array like ["a", "b", "c"]
    """
    try:
        value = float(value)
    except:
        value = 0
    if isinstance(keys, basestring):
        keys = keys.split('.')
    pre_dict = dict
    for i in xrange(len(keys)):
        if keys[i] not in pre_dict:
            if i == len(keys) - 1:
                pre_dict[keys[i]] = value
            else:
                pre_dict[keys[i]] = {}
        else:
            if i == len(keys) - 1:
                pre_dict[keys[i]] += value
        pre_dict = pre_dict[keys[i]]