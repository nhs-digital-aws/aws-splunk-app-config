
"""
Add usage example here for splunksdc.log
Usage::
Working with main thread logging and passing context to sub-threads

>>> def worker(*params, outer_context):
>>>     with LogContext(parent_ctx=outer_context) as ctx:
>>>         print params
>>>         pass

# Using the with syntax:
>>> import splunksdc.log as logging

>>> root = logging.setup_root_logger(app_name=app, mudular_name=mod, stanza_name=stanza)
>>> logger = logging.get_context_logger(logger_name)

>>> with logging.LogContext('context_1'='value', 'context_2'='value2') as ctx:
>>>     logger.error('Error messgae', key=value, key2=value2)
>>>     with logging.LogContext('context_inner_1'='v1', 'context_inner_2'=v2) as ctx_2:
>>>         logger.info('Info messgae', key=value, key2=value2)
>>>         t1 = threading.Thread(target=worker, args=('foo', ctx_2))
>>>         t1.start()
>>>         t1.join()
"""

from __future__ import absolute_import
import json.encoder as encode
import logging as log4py
from logging import LoggerAdapter, Formatter
from logging import INFO, WARNING, DEBUG, ERROR, FATAL, StreamHandler
from logging.handlers import RotatingFileHandler
import re
import os
import threading
import sys
from splunksdc import environ


__all__ = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'FATAL', 'StreamHandler',
           'RotatingFileHandler', 'LogContextAdapter',
           'get_context_logger', 'DefaultHandlerFactory',
           'ThreadLocalLoggingStack', 'LogContext']


encode_basestring = encode.encode_basestring


def _dict2str(kv):
    kvs = []
    for key, value in kv.iteritems():
        if isinstance(value, unicode):
            value = value.encode('utf-8')
        if isinstance(value, str):
            value = encode_basestring(value)
        kvs.append('{0}={1}'.format(key, value))
    return ' '.join(kvs)


class ThreadLocalLoggingStack(object):
    """
    ThreadLocalLoggingStack leverages thread local storage to store context
    for logging. It provides interfaces like a usual stack data structure.
    Since it leverages thread local, there is one and only one instance of
    this stack can be created per thread
    """

    _data = threading.local()

    @classmethod
    def _context_stack(cls):
        cls.create()
        return cls._data.logging_context_stack

    @classmethod
    def create(cls):
        if not hasattr(cls._data, 'logging_context_stack'):
            cls._data.logging_context_stack = []
        return cls

    @classmethod
    def top(cls, default=''):
        if not cls.empty():
            return cls._data.logging_context_stack[-1]
        else:
            return default

    @classmethod
    def empty(cls):
        return not (hasattr(cls._data, 'logging_context_stack') and
                    cls._data.logging_context_stack)

    @classmethod
    def push(cls, prefix=None, **kwargs):
        parts = []
        if cls.top():
            parts.append(cls.top())
        if prefix:
            parts.append(prefix)
        if kwargs:
            trans = _dict2str(kwargs)
            parts.append(trans)
        ctx = ', '.join(parts)
        cls.append(ctx)
        return ctx

    @classmethod
    def append(cls, ctx):
        cls._context_stack().append(ctx)

    @classmethod
    def pop(cls):
        if not cls.empty():
            cls._context_stack().pop()


class LogContext(object):
    """
    The LogContext class is for easy appending new context info.
    Supports with syntax.

    """

    def __init__(self, prefix=None, **kwargs):
        """
        :param prefix: string return by other threads's
                            ThreadLocalLoggingStack.top()
        :param kwargs: k-v context info, will be appended
                        to current context stack top

        """

        self.ctx_stack = ThreadLocalLoggingStack()
        self.prefix = prefix
        self.kwargs = kwargs

    def __enter__(self):
        return self.ctx_stack.push(prefix=self.prefix, **self.kwargs)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.ctx_stack:
            self.ctx_stack.pop()


class ContextLoggerAdapter(LoggerAdapter):
    """
    Customized the LoggerAdapter class.
    This class fetches the latest context from thread local
    context stack and supports logging the context in a k-v mode.
    """

    def __init__(self, logger):
        super(ContextLoggerAdapter, self).__init__(logger, None)
        # Add aliases for compatibility
        self.warn = self.warning
        self.fatal = self.critical

        # Added to imitate stdlib logger behavior, for backward compatibility.
        self.setLevel = self.set_level

    @staticmethod
    def _top():
        thread_context = ThreadLocalLoggingStack()
        return thread_context.top(default='')

    def process(self, msg, kwargs):
        try:
            opts = {
                'exc_info': kwargs.pop('exc_info', None),
                'extra': kwargs.pop('extra', {})
            }
            opts['extra']['_context'] = self._top()
            opts['extra']['_kwargs'] = _dict2str(kwargs)
            return msg, opts
        except Exception:
            self.logger.exception('Failed to process records. | %s %s', msg, kwargs)
            return msg, {}

    def set_level(self, level):
        """
        :param level: integer level
        :return:
        """
        if self.logger:
            self.logger.setLevel(level)


def get_context_logger(name=None):
    """
    Helper function which returns a context logger for a logger.
    :param name: logger name
    :return: context adapter for logger
    """
    logger = log4py.getLogger(name)
    context_adapter = ContextLoggerAdapter(logger)
    return context_adapter


def get_module_logger(prefix=None):
    frame = sys._getframe(1)
    name = frame.f_globals['__name__']
    if prefix:
        name = prefix + '.' + name
    return get_context_logger(name)


def setup_root_logger(app_name=None, modular_name=None, stanza_name=None, logging_level=WARNING):
    """
    Helper function for root logger setup, called only once for each process.
    :param app_name: string
    :param modular_name: string
    :param stanza_name: string
    :param logging_level: integer, default to WARNING to prevent from
     third party logs flooding
    :return: None
    """
    factory = RotatingFileHandlerFactory(app_name, modular_name, stanza_name)
    RootHandler.setup(factory)
    log4py.root.setLevel(logging_level)


class RootHandler(object):
    _handler = None

    @classmethod
    def setup(cls, factory, formatter=None):
        if cls._handler:
            raise ValueError('RootHandler already exists.')
        cls._handler = factory()
        if not formatter:
            formatter = ContextualLogFormatter(False)
        cls._handler.setFormatter(formatter)
        log4py.root.addHandler(cls._handler)

    @classmethod
    def teardown(cls):
        if not cls._handler:
            return
        log4py.root.removeHandler(cls._handler)
        cls._handler.close()
        cls._handler = None


class StreamHandlerFactory(object):
    def __init__(self, stream=sys.stderr):
        self._stream = stream

    def __call__(self, stream=sys.stderr):
        handler = StreamHandler(stream=self._stream)
        return handler


class RotatingFileHandlerFactory(object):
    def __init__(self, app_name=None, modular_name=None, stanza_name=None):
        self._app_name = app_name
        self._modular_name = modular_name
        self._stanza_name = stanza_name

    def __call__(self):
        """
        Returns the default handlers.
        :return:
        """
        filename = self._assemble_file_name()
        log_dir = environ.get_log_folder()
        filepath = os.path.join(log_dir, filename)
        # Make the file handle not inheritable on Windows
        handler = RotatingFileHandler(
            filepath, maxBytes=1024 * 1024 * 25, backupCount=5, delay=True
        )
        if os.name == 'nt':
            handler.mode = 'aN'
        return handler

    def _assemble_file_name(self):
        name_parts = []
        app_name = ''
        if self._app_name is not None:
            app_name = self._app_name.replace('-', '_')
            app_name = app_name.lower()
            name_parts.append(app_name)
        if self._modular_name is not None:
            modular_name = self._modular_name.replace('-', '_')
            modular_name = modular_name.lower()
            if modular_name.startswith(app_name):
                modular_name = modular_name.replace(app_name, '')
                modular_name = modular_name.strip('_')
            name_parts.append(modular_name)
        if self._stanza_name:
            name_parts.append(self._stanza_name)
        filename = '_'.join(name_parts)
        if not filename:
            filename = 'temp_logs_file'
        filename += '.log'
        filename = re.sub(r'[<>?*:|/\"]', '_', filename)
        return filename


class ContextualLogFormatter(object):
    def __init__(self, internal=False):
        prefix = ''.join([
            '%(asctime)s level=%(levelname)s pid=%(process)d tid=%(threadName)s ',
            'logger=%(name)s pos=%(filename)s:%(funcName)s:%(lineno)s '
        ])
        if internal:
            prefix = ''.join([
                '%(levelname)s logger=%(name)s pid=%(process)d tid=%(threadName)s ',
                'logger=%(name)s pos=%(filename)s:%(funcName)s:%(lineno)s '
            ])
        kv = prefix + '| %(_context)s | message="%(message)s" %(_kwargs)s'
        raw = prefix + '| %(message)s'
        self._kv = Formatter(kv)
        self._raw = Formatter(raw)

    def format(self, record):
        if hasattr(record, '_context') and hasattr(record, '_kwargs'):
            return self._kv.format(record)
        return self._raw.format(record)
