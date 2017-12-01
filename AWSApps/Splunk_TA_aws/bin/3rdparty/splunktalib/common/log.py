"""
Copyright (C) 2005-2015 Splunk Inc. All Rights Reserved.

log utility for TA
"""

import logging


logger = logging.getLogger('splunktalib')


def log_enter_exit(logger):
    """
    Log decorator to log function enter and exit
    """
    def log_decorator(func):
        def wrapper(*args, **kwargs):
            logger.debug("%s entered.", func.__name__)
            result = func(*args, **kwargs)
            logger.debug("%s exited.", func.__name__)
            return result
        return wrapper
    return log_decorator


class Logs(object):
    """
    This class should be removed in near future.
    This logger only intent to be used by splunktalib itself.
    """
    def __init__(self, *args, **kwargs):
        """
        All parameters here don't have any effect anymore.
        """
        pass

    def get_logger(self, *args, **kwargs):
        """
        All parameters here don't have any effect anymore.
        """
        return logger

    def set_level(self, level, *args, **kwargs):
        """
        All parameters except level here don't have any effect anymore.
        """
        logger.setLevel(level)
