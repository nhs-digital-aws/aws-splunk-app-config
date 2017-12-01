"""
Example:
    XMLEventWriter support both event mode and chunk mode.
    
    metadata = {source:..., sourcetype: ..., host:..., index:...}
    device = XMLEventWriter(lock, sys.stdout, **metadata)
    
    device.write_events(['data1', 'data2'])
    device.write_fileobj(fileobj)
        
    So far, HECWriter support chunk mode only.
    
    device = HECWriter('https://127.0.0.1:8088/HEC_TOKEN', **metadata)
    device.write_fileobj(fileobj)
        
"""
import requests
import uuid
import cStringIO as StringIO
from datetime import datetime
from urlparse import urljoin, urlparse
from xml.sax import saxutils
from splunksdc import log as logging


logger = logging.get_module_logger()


class EventWriter(object):

    _METADATA_KEYS = ['source', 'sourcetype', 'host', 'index']

    def __init__(self):
        self._chunk_size = 4 * 1024 * 1024

    def _read_multiple_lines(self, stream):
        fileobj = stream
        if isinstance(fileobj, str):
            fileobj = StringIO.StringIO(stream)

        chunk_size = self._chunk_size
        chunk = ''
        while True:
            available = chunk_size - len(chunk)
            chunk += fileobj.read(available)
            if not chunk:
                break

            # the last chunk
            if len(chunk) < chunk_size:
                yield chunk
                break

            last_newline = chunk.rfind('\n')
            # no new line found or last chunk gotten
            if last_newline == -1:
                yield chunk
                chunk = ''
                continue

            boundary = last_newline + 1
            yield chunk[:boundary]
            chunk = chunk[boundary:]


class XMLEventWriter(EventWriter):
    """
    XML event writer
    """
    _EVENT_TEMPLATE = '<stream><event {stanza}>{source}{sourcetype}{host}{index}{data}{time}</event></stream>'

    _CHUNK_TEMPLATE = '<stream>' \
                      '<event unbroken="1" {stanza}>' \
                      '{source}{sourcetype}{host}{index}{data}{done}' \
                      '</event>' \
                      '</stream>'

    _EPOCH = datetime(1970, 1, 1)

    @classmethod
    def _render_element(cls, key, value):
        value = saxutils.escape(value)
        value = '<{0}>{1}</{0}>'.format(key, value)
        return value

    @classmethod
    def _render_attribute(cls, key, value):
        value = saxutils.escape(value)
        value = '{0}="{1}"'.format(key, value)
        return value

    @classmethod
    def _render_timestamp(cls, key, value):
        if isinstance(value, datetime):
            value = int((value - cls._EPOCH).total_seconds())
        return '<{0}>{1}</{0}>'.format(key, value)

    @classmethod
    def _ensure_utf8_compatible(cls, data):
        if isinstance(data, str):
            data = data.decode('utf-8', errors='replace')
        return data.encode('utf-8')

    @classmethod
    def _render_metadata(cls, kwargs):
        metadata = {}
        for key, value in kwargs.items():
            if not value:
                continue
            if key in cls._METADATA_KEYS:
                metadata[key] = cls._render_element(key, value)
            elif key == 'stanza':
                metadata[key] = cls._render_attribute(key, value)
        return metadata

    @classmethod
    def _render_defaults(cls, kwargs):
        defaults = {key: '' for key in cls._METADATA_KEYS}
        defaults['stanza'] = ''
        metadata = cls._render_metadata(kwargs)
        defaults.update(metadata)
        return defaults

    def __init__(self, lock, dev, **kwargs):
        super(XMLEventWriter, self).__init__()
        self._lock = lock
        self._dev = dev
        self._defaults = self._render_defaults(kwargs)

    def _write(self, data):
        with self._lock:
            self._dev.write(data)
            self._dev.flush()

    def _compose_event_metadata(self, kwargs):
        composed = dict(self._defaults)
        composed.update(self._render_metadata(kwargs))
        return composed

    def write_events(self, events, timestamp=None, **kwargs):
        volume = 0
        metadata = self._compose_event_metadata(kwargs)
        logger.debug('Start writing events to STDOUT.', **metadata)
        for data in events:
            volume += len(data)
            data = self._render_element('data', data)
            time = '' if not timestamp else timestamp(data)
            time = self._render_timestamp('time', time)
            data = self._EVENT_TEMPLATE.format(data=data, time=time, **metadata)
            self._write(data)
        logger.debug('Wrote events to STDOUT success.', size=volume)
        return volume

    def write_fileobj(self, fileobj, **kwargs):
        volume = 0
        metadata = self._compose_event_metadata(kwargs)
        logger.debug('Start writing data to STDOUT.', **metadata)
        for chunk in self._read_multiple_lines(fileobj):
            volume += len(chunk)
            data = self._render_element('data', chunk)
            data = self._CHUNK_TEMPLATE.format(data=data, done='', **metadata)
            self._write(data)
        eos = self._CHUNK_TEMPLATE.format(data='', done='<done/>', **metadata)
        self._write(eos)
        logger.debug('Wrote data to STDOUT success.', size=volume)
        return volume


class HECError(Exception):
    def __init__(self, response):
        super(HECError, self).__init__(response.content)
        self._response = response

    @property
    def status_code(self):
        return self._response.status_code


class HECWriter(EventWriter):

    @classmethod
    def _render_metadata(cls, kwargs):
        metadata = {}
        for key, value in kwargs.items():
            if key in cls._METADATA_KEYS and value:
                metadata[key] = value
        return metadata

    def __init__(self, url, **kwargs):
        super(HECWriter, self).__init__()
        parts = urlparse(url)
        token = parts.path[1:]
        self._base = parts.scheme + '://' + parts.netloc
        self._auth_header = {'Authorization': 'Splunk {}'.format(token)}
        self._session = requests.Session()
        self._defaults = self._render_metadata(kwargs)
        self._uuid = uuid.uuid4

    def _post(self, path, data, params, headers):
        url = urljoin(self._base, path)
        return self._session.post(url, data, params=params, headers=headers, verify=False)

    def _compose_event_metadata(self, kwargs):
        composed = dict(self._defaults)
        composed.update(self._render_metadata(kwargs))
        return composed

    def write_events(self, events, timestamp=None, **kwargs):
        raise NotImplementedError()

    def write_fileobj(self, fileobj, **kwargs):
        """
        :param fileobj: a readable file object.
        """
        volume = 0
        channel = kwargs.get('channel', self._uuid())
        path = '/services/collector/raw'
        headers = {'X-Splunk-Request-Channel': str(channel)}
        headers.update(self._auth_header)
        metadata = self._compose_event_metadata(kwargs)
        logger.debug('Start writing data to RawHEC.', **metadata)
        for chunk in self._read_multiple_lines(fileobj):
            volume += len(chunk)
            response = self._post(path, chunk, metadata, headers)
            if response.status_code != 200:
                logger.error('Sent chunk failed.', status_code=response.status_code, text=response.text)
                raise HECError(response)
        logger.debug('Wrote data via RawHEC success.', size=volume)
        return volume




