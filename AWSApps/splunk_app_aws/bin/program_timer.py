__author__ = 'peter'

import time
import utils.app_util as util

logger = util.get_logger()


class ProgramTimer:
    def __init__(self, name):
        self.name = name
        self.start = self.end = time.time()

    def stop(self):
        self.end = time.time()
        logger.info("Performance track [ %s ] : %.3f ms" % (self.name, (self.end - self.start)*1000))
