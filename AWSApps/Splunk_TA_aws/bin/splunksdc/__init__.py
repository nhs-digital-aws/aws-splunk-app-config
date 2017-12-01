import splunksdc.log as logging

__version__ = '1.0'

logger = logging.get_module_logger()
logger.set_level(logging.INFO)


def set_log_level(level):
    logger.set_level(level)
