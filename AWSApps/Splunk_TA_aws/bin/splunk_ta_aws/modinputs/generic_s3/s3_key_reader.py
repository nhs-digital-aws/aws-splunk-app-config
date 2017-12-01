import tarfile
import zipfile
import gzip
import cStringIO as cio

import aws_s3_consts as asc
import aws_s3_common as s3common


# Note always use `for data in reader` to consume data


def read_all(reader):
    chunks = []
    for chunk in reader:
        chunks.append(chunk)
    return "".join(chunks)


class S3KeyReader(object):

    bufsize = 8192

    def __init__(self, config, logger):
        """
        :config: dict
        {
           key_object: xxx (Boto S3 Key object):
           key: yyy (string key name),
           key_id: xxx (string, AWS credentials),
           secret_key: yyy (string, AWS credentials),
           bucket_name: xxx,
           offset: xxx,
        }
        """

        self._config = config
        self._logger = logger
        if config.get(asc.key_object) is None:
            self._get_key_object()
        self._read_pos = 0
        self._whence = 0
        self._total_size = self._config[asc.key_object].size
        self._reached_eof = False
        self._iter = None

    def seek(self, offset, whence=0):
        """
        Mimic the file.seek in Python
        """

        assert self._config[asc.key_object] is not None

        if whence == 1 and offset == 0:
            return

        pos = self._read_pos
        if whence == 0:
            pos = offset
        elif whence == 2:
            assert pos >= 0
            if offset == 0:
                pos = self._total_size
            elif offset < 0:
                pos = self._total_size + offset
        else:
            assert whence == 1
            pos = pos + offset
            assert pos >= 0

        if pos == self._total_size:
            byte_range = "bytes={}".format(pos)
        else:
            byte_range = "bytes={}-".format(pos)

        headers = {"Range": byte_range}

        self._config[asc.key_object].close(fast=False)
        self._config[asc.key_object].open_read(headers=headers)
        self._whence = whence
        self._read_pos = pos

    def tell(self):
        """
        providing this function for zip reader
        """

        return self._read_pos

    def reached_eof(self):
        return self._reached_eof

    def __iter__(self):
        if self._iter is None:
            self._iter = self.next()
        return self._iter

    def read(self, size=0):
        """
        :size: read size bytes from s3 key if size > 0,
        otherwise read all bytes from key. Providing this function for
        zip/tar reader.
        """

        assert self._config[asc.key_object] is not None

        if size == 0:
            size = self.bufsize

        data = self._config[asc.key_object].read(size)
        if data:
            self._read_pos += len(data)
        else:
            self._reached_eof = True

        return data

    def next(self):
        assert self._config[asc.key_object] is not None

        key = self._config[asc.key_object]
        bufsize = self.bufsize
        while 1:
            data = key.read(bufsize)
            if not data:
                self._reached_eof = True
                break
            self._read_pos += len(data)
            yield data

    def key_object(self):
        return self._config[asc.key_object]

    def _get_key_object(self):
        conn = s3common.create_s3_connection(self._config)
        bucket = conn.get_bucket(self._config[asc.bucket_name])
        self._config[asc.key_object] = bucket.get_key(self._config[asc.key])
        if self._config[asc.key_object] is None:
            msg = "Failed to get S3 object."
            self._logger.error(msg, key=self._config[asc.key])
            raise Exception(msg)

    def read_all(self):
        return read_all(self)

    def close(self, fast=False):
        self._config[asc.key_object].close(fast=fast)

    def size(self):
        return self._total_size


class S3KeyPackageReader(object):

    def __init__(self, config, logger):
        s3reader = S3KeyReader(config, logger)
        self._key_object = s3reader.key_object()
        self._raw_size = s3reader.size()
        if self._raw_size <= 8192:
            logger.debug("Use perf enhanced s3 reader")
            data = s3reader.read_all()
            s3reader.close()
            s3reader = cio.StringIO(data)

        self._s3reader = s3reader
        self._read_pos = 0
        self._seek_left = ""
        self._iter = None

    def __iter__(self):
        if self._iter is None:
            self._iter = self.next()
        return self._iter

    def size(self):
        return self._raw_size

    def seek(self, offset, whence=0):
        """
        only support seek from beginning
        """

        self._seek_left = self._discard(offset)
        self._read_pos = offset

    def tell(self):
        return self._read_pos

    def _discard(self, size):
        for data in self:
            if size < len(data):
                return data[size:]

            size -= len(data)
            if size <= 0:
                break

        return ""

    def key_object(self):
        return self._key_object

    def read_all(self):
        return read_all(self)

    def close(self, fast=False):
        if isinstance(self._s3reader, S3KeyReader):
            return self._s3reader.close(fast=fast)
        else:
            return self._s3reader.close()

    def next(self):
        raise NotImplementedError("Derived class should implement")


class S3KeyTarReader(S3KeyPackageReader):

    def __init__(self, config, logger):
        super(S3KeyTarReader, self).__init__(config, logger)
        self._package_reader = tarfile.open(None, "r|*", self._s3reader)

    def next(self):
        tar_reader = self._package_reader
        for member in tar_reader:
            if not member:
                continue

            if not member.isfile():
                continue

            extracted = tar_reader.extractfile(member)
            while 1:
                if self._seek_left:
                    data, self._seek_left = self._seek_left, ""
                    self._read_pos += len(self._seek_left)
                    yield data

                data = extracted.read(S3KeyReader.bufsize)
                if data:
                    self._read_pos += len(data)
                    yield data
                    if extracted.size == extracted.tell():
                        break
                else:
                    break


class S3KeyGzipReader(S3KeyPackageReader):

    def __init__(self, config, logger):
        super(S3KeyGzipReader, self).__init__(config, logger)
        self._package_reader = gzip.GzipFile(fileobj=self._s3reader)

    def next(self):
        gzip_reader = self._package_reader
        while 1:
            if self._seek_left:
                data, self._seek_left = self._seek_left, ""
                self._read_pos += len(self._seek_left)
                yield data

            data = gzip_reader.read(S3KeyReader.bufsize)
            if not data:
                break

            self._read_pos += len(data)
            yield data


class S3KeyZipReader(S3KeyPackageReader):
    """
    Only support one file in zipped. Nested zip/gzip etc or folders in zipped
    is not supported for now
    """

    def __init__(self, config, logger):
        super(S3KeyZipReader, self).__init__(config, logger)
        zipfile.ZipExtFile.MIN_READ_SIZE = 8192
        self._package_reader = zipfile.ZipFile(self._s3reader)

    def next(self):
        zip_reader = self._package_reader
        for f in zip_reader.filelist:
            with zip_reader.open(f) as zf:
                while 1:
                    if self._seek_left:
                        self._read_pos += len(self._seek_left)
                        yield self._seek_left
                        self._seek_left = ""

                    data = zf.read(S3KeyReader.bufsize)
                    if not data:
                        break

                    self._read_pos += len(data)
                    yield data


def create_s3_key_reader(config, logger):
    """
    :config: dict
    {
       key_object: xxx (Boto S3 Key object):
       key: yyy (string key name),
       key_id: xxx (string, AWS credentials),
       secret_key: yyy (string, AWS credentials),
       bucket_name: xxx,
    }
    Create a correct S3 key reader accoring to the postfix of the key name
    """

    if config.get(asc.key_object) is not None:
        key_name = config[asc.key_object].name
    else:
        assert config[asc.key]
        key_name = config[asc.key]

    if (key_name.endswith(".tar") or key_name.endswith(".tar.bz2") or
            key_name.endswith(".tar.gz") or key_name.endswith(".tgz")):
        return S3KeyTarReader(config, logger)
    elif key_name.endswith(".zip"):
        return S3KeyZipReader(config, logger)
    elif key_name.endswith(".gz"):
        return S3KeyGzipReader(config, logger)
    return S3KeyReader(config, logger)
