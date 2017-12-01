import splunksdc
import splunksdc.log as logging


logger = logging.get_module_logger()
logger.set_level(logging.INFO)


def set_log_level(level):
    logger.set_level(level)
    splunksdc.set_log_level(level)
