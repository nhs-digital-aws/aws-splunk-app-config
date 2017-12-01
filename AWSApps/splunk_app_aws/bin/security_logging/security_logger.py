__author__ = 'pj'

import logging
import traceback
from esapi.codecs.css import CSSCodec
from esapi.codecs.html_entity import HTMLEntityCodec
from esapi.codecs.percent import PercentCodec
from esapi.codecs.javascript import JavascriptCodec
from exception import IntrusionException
from security_encoder import SecurityEncoder


class SecurityLogger(logging.LoggerAdapter):
    def __init__(self, logger, extra={}):
        self.logger = logger
        self.extra = extra
        # Enable code for html, JS, url and CSS
        codeclist = [HTMLEntityCodec(), JavascriptCodec(), PercentCodec(), CSSCodec()]
        self.encoder = SecurityEncoder(codeclist)

    def setLevel(self, level):
        self.logger.setLevel(level)

    def process(self, msg, kwargs):
        """
            Encode message in order to prevent log injection.
            This function will be called before calling debug, info, etc function.
        """
        # ensure there's something to log
        if msg is None:
            msg = ""

        kwargs["extra"] = self.extra
        clean = ""
        try:
            clean = self.encoder.canonicalize(msg)
            if msg != clean:
                clean += " (Encoded)"
        except IntrusionException:
            stack = traceback.format_exc()
            self.logger.info(str(stack))
        finally:
            return clean, kwargs
