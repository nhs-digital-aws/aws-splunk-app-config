from collections import namedtuple
import cStringIO as StringIO
import codecs
import json
from splunksdc import logging
from splunksdc.archive import ArchiveFactory

logger = logging.get_module_logger()


Metadata = namedtuple('Metadata', ['source', 'sourcetype'])


class Decoder(object):
    def __init__(self, **kwargs):
        self._af = ArchiveFactory.create_default_instance()

    def __call__(self, fileobj, source):
        raise NotImplementedError()

    def _open(self, fileobj, filename):
        return self._af.open(fileobj, filename)

    @staticmethod
    def _product_multiple_lines(sequence):
        lines = [line for line in sequence]
        lines.append('')
        return '\n'.join(lines)


class CloudTrailLogsDecoder(Decoder):
    def __call__(self, fileobj, source):
        for member, uri in self._open(fileobj, source):
            document = json.load(member)
            if self._is_digest(document):
                logger.info('Ignore CloudTail digest file.', source=source)
                continue
            records = document['Records']
            records = (json.dumps(item) for item in records)
            records = self._product_multiple_lines(records)
            yield records, Metadata(uri, 'aws:cloudtrail')

    @staticmethod
    def _is_digest(document):
        return 'Records' not in document


class ELBAccessLogsDecoder(Decoder):
    def __call__(self, fileobj, source):
        for member, uri in self._open(fileobj, source):
            yield UTFStreamDecoder.create(member), Metadata(uri, 'aws:elb:accesslogs')


class CloudFrontAccessLogsDecoder(Decoder):
    def __call__(self, fileobj, source):
        for member, uri in self._open(fileobj, source):
            yield UTFStreamDecoder.create(member), Metadata(uri, 'aws:cloudfront:accesslogs')


class S3AccessLogsDecoder(Decoder):
    def __call__(self, fileobj, source):
        for member, uri in self._open(fileobj, source):
            yield UTFStreamDecoder.create(member), Metadata(uri, 'aws:s3:accesslogs')


class ConfigDecoder(Decoder):
    def __call__(self, fileobj, source):
        for member, uri in self._open(fileobj, source):
            document = json.load(member)
            records = document['configurationItems']
            records = (json.dumps(item) for item in records)
            records = self._product_multiple_lines(records)
            yield records, Metadata(source, 'aws:config')


class CustomLogsDecoder(Decoder):
    def __init__(self, **kwargs):
        super(CustomLogsDecoder, self).__init__()
        self._sourcetype = kwargs.get('sourcetype', '')

    def __call__(self, fileobj, source):
        for member, uri in self._open(fileobj, source):
            yield UTFStreamDecoder.create(member), Metadata(uri, self._sourcetype)


class UTFStreamDecoder(object):
    # keep longer signature ahead
    _BOM_SIGNATURE = [
        (codecs.BOM_UTF32_LE, 'utf-32-le'),
        (codecs.BOM_UTF32_BE, 'utf-32-be'),
        (codecs.BOM_UTF8, 'utf-8-sig'),
        (codecs.BOM_UTF16_LE, 'utf-16-le'),
        (codecs.BOM_UTF16_BE, 'utf-16-be'),
    ]

    @classmethod
    def _create_decoder(cls, head):
        encoding = 'utf-8'
        for signature, name in cls._BOM_SIGNATURE:
            if head.startswith(signature):
                encoding = name
                break
        factory = codecs.getincrementaldecoder(encoding)
        decoder = factory(errors='replace')
        return decoder

    @classmethod
    def create(cls, fileobj):
        if isinstance(fileobj, str):
            fileobj = StringIO.StringIO(fileobj)
        head = fileobj.read(4096)
        decoder = cls._create_decoder(head)
        obj = cls(decoder, fileobj)
        obj._decode(head)
        return obj

    def __init__(self, decoder, fileobj):
        self._fileobj = fileobj
        self._decoder = decoder
        self._pending = ''
        self._exhausted = False
        self._chunk_size = 4 * 1024 * 1024

    def _next_chunk(self):
        return self._fileobj.read(self._chunk_size)

    def _decode(self, data=''):
        final = False if data else True
        self._pending += self._decoder.decode(data, final=final).encode('utf-8')

    def read(self, size):
        while len(self._pending) < size and not self._exhausted:
            chunk = self._next_chunk()
            if not chunk:
                self._decode()
                self._exhausted = True
                break
            self._decode(chunk)

        chunk = self._pending[:size]
        self._pending = self._pending[size:]
        return chunk


class DecoderFactory(object):
    @classmethod
    def create_default_instance(cls):
        factory = cls()
        factory.register('CustomLogs', CustomLogsDecoder)
        factory.register('CloudTrail', CloudTrailLogsDecoder)
        factory.register('ELBAccessLogs', ELBAccessLogsDecoder)
        factory.register('CloudFrontAccessLogs', CloudFrontAccessLogsDecoder)
        factory.register('S3AccessLogs', S3AccessLogsDecoder)
        factory.register('Config', ConfigDecoder)
        return factory

    def __init__(self):
        self._registry = dict()

    def create(self, name, **kwargs):
        name = name.lower()
        decoder_type = self._registry.get(name)
        return decoder_type(**kwargs)

    def register(self, name, decode_type):
        name = name.lower()
        self._registry[name] = decode_type
