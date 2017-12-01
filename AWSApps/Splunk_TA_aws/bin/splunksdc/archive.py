import tarfile
import zipfile
import gzip
from splunksdc import log as logging


logger = logging.get_module_logger()


class Archive(object):
    def __init__(self, fileobj, filename):
        self._fileobj = fileobj
        self._filename = filename

    def __iter__(self):
        self._fileobj.seek(0)
        return self._items()

    def _items(self):
        raise NotImplementedError()


class GeneralFile(Archive):
    def _items(self):
        yield self._fileobj, self._filename


class TarArchive(Archive):
    def _items(self):
        with tarfile.open(mode='r|*', fileobj=self._fileobj) as archive:
            for tarinfo in archive:
                member = archive.extractfile(tarinfo)
                if not member:
                    logger.warning('Extract tar member failed.')
                    continue
                yield member, self._filename + '/' + tarinfo.name


class GzipArchive(Archive):
    def _items(self):
        with gzip.GzipFile(mode='r', fileobj=self._fileobj) as member:
            yield member, self._filename


class ZipArchive(Archive):
    def _items(self):
        with zipfile.ZipFile(self._fileobj) as archive:
            for name in archive.namelist():
                with archive.open(name) as member:
                    yield member, self._filename + '/' + name


class ArchiveFactory(object):
    @classmethod
    def create_default_instance(cls):
        factory = cls()
        factory.register(['.tar', '.tar.gz', '.tar.bz2', '.tgz'], TarArchive)
        factory.register(['.gz', '.gzip'], GzipArchive)
        factory.register(['.zip'], ZipArchive)
        return factory

    def __init__(self):
        self._registry = {}

    def register(self, suffixes, archive_type):
        for ext in suffixes:
            self._registry[ext] = archive_type

    def open(self, fileobj, filename):
        first_dot = filename.find('.')
        ext = filename[first_dot:] if first_dot != -1 else ''
        ext = ext.lower()
        matches = [key for key in self._registry.keys() if ext.endswith(key)]
        matches = sorted(matches, key=lambda x: len(x), reverse=True)
        if matches:
            ext = matches[0]
            archive_type = self._registry[ext]
            return archive_type(fileobj, filename)
        return GeneralFile(fileobj, filename)




