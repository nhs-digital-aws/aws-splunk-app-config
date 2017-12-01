__author__ = 'pezhang'

STRICTNESS_MAP = {'h': 1, 'm': 2, 'l': 3}
STRICTNESS_LIST = ['l', 'h', 'm']
TRAIN_COUNT = 10


def get_severity(deviation):
    if deviation <= 4:
        return 1
    elif deviation <= 5:
        return 2
    elif deviation <= 6:
        return 3
    else:
        return 4
