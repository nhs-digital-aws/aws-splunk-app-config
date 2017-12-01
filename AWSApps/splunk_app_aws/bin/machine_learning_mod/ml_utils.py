__author__ = 'frank'

import logging, os
import logging.handlers as handlers

LOG_NAME = 'machine_learning'


def create_logger_handler(fd, level, max_bytes=10240000, backup_count=5):
    handler = handlers.RotatingFileHandler(fd, maxBytes=max_bytes, backupCount=backup_count)
    handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] [%(filename)s] %(message)s'))
    handler.setLevel(level)
    return handler


def get_logger(level=logging.INFO):
    logger = logging.Logger(LOG_NAME)
    LOG_FILENAME = os.path.join(os.environ.get('SPLUNK_HOME'), 'var', 'log', 'splunk', '%s.log' % LOG_NAME)
    logger.setLevel(level)
    handler = create_logger_handler(LOG_FILENAME, level)
    logger.addHandler(handler)
    return logger