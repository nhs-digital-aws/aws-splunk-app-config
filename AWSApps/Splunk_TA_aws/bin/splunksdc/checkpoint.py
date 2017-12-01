import os
import os.path
import binascii
import time
from sortedcontainers import sorteddict
import umsgpack
from splunksdc import log as logging

logger = logging.get_module_logger()


class BucketFileError(Exception):
    def __init__(self, message, valid_data_size):
        super(BucketFileError, self).__init__(message)
        self._valid_data_size = valid_data_size

    @property
    def valid_data_size(self):
        return self._valid_data_size


class Item(object):
    def __init__(self, key, value):
        self._key = key
        self._value = value

    @property
    def key(self):
        return self._key

    @property
    def value(self):
        return self._value


class Partition(object):
    def __init__(self, store, prefix):
        self._store = store
        self._prefix = prefix
        self._prefix_size = len(prefix)

    def _decor(self, key):
        return self._prefix + key

    def _strip(self, key):
        return key[self._prefix_size:]

    def _raw_keys(self):
        return self._store.prefix(self._prefix)

    def empty(self):
        for _ in self._raw_keys():
            return False
        return True

    def items(self):
        for key in self._raw_keys():
            yield self._strip(key), self._store.get(key)

    def delete(self, key):
        key = self._decor(key)
        self._store.delete(key)

    def set(self, key, value):
        key = self._decor(key)
        self._store.set(key, value)

    def keys(self):
        for key in self._raw_keys():
            yield self._strip(key)


class LocalKVStore(object):
    MAGIC = 'BUK0'
    OP_DELETE = 0
    OP_SET = 1

    @classmethod
    def _replay(cls, fp):
        fp.seek(0, os.SEEK_END)
        end = fp.tell()
        fp.seek(0, os.SEEK_SET)

        magic = fp.read(4)
        if magic != 'BUK0':
            raise BucketFileError('magic mismatch', 0)
        while True:
            position = fp.tell()
            if position >= end:
                break
            try:
                flag, key, _ = umsgpack.unpack(fp)
                if flag not in [cls.OP_DELETE, cls.OP_SET]:
                    raise BucketFileError('data corrupted', position)
            except umsgpack.InsufficientDataException:
                raise BucketFileError('data corrupted', position)
            else:
                yield flag, key, position
        raise StopIteration()

    @classmethod
    def _flush(cls, fp):
        fp.flush()
        # fn = fp.fileno()
        # os.fsync(fn)

    @classmethod
    def _append(cls, flag, key, value, fp, **kwargs):
        fp.seek(0, 2)
        entry = (flag, key, value)
        umsgpack.pack(entry, fp)
        if kwargs.pop('flush', True):
            cls._flush(fp)

    @classmethod
    def _truncate(cls, fp, size):
        if size == 0:
            fp.truncate(0)
            fp.write(cls.MAGIC)
        else:
            fp.truncate(size)
            fp.seek(0, 2)
        cls._flush(fp)

    @classmethod
    def _remove(cls, path):
        time.sleep(1)
        for count in range(3):
            try:
                os.remove(path)
            except OSError:
                logger.exception('Remove checkpoint failed.', path=path, tried=count)
                time.sleep(1)
            else:
                break

    @classmethod
    def _replace_file(cls, src, dst):
        if os.name == 'nt':
            cls._remove(dst)
        try:
            os.rename(src, dst)
        except OSError:
            logger.exception('Replace checkpoint failed.', src=src, dst=dst)

    @classmethod
    def _read(cls, pos, fp):
        fp.seek(pos, os.SEEK_SET)
        entry = umsgpack.unpack(fp)
        _, _, value = entry
        return value

    @classmethod
    def open_always(cls, filename):
        fp = open(filename, 'a+b')
        indexes = cls.build_indexes(fp)
        return cls(indexes, fp)

    @classmethod
    def build_indexes(cls, fp):
        indexes = sorteddict.SortedDict()
        try:
            for flag, key, pos in cls._replay(fp):
                if flag == cls.OP_DELETE:
                    del indexes[key]
                    logger.debug('Key was deleted.', key=key, pos=pos)
                elif flag == cls.OP_SET:
                    indexes[key] = pos
                    logger.debug('Key was set.', key=key, pos=pos)
        except BucketFileError as e:
            cls._truncate(fp, e.valid_data_size)
        return indexes

    @classmethod
    def nearest_greater_prefix(cls, prefix):
        hexstr = binascii.b2a_hex(prefix)
        hexnum = long(hexstr, 16)
        hexnum += 1
        hexstr = hex(hexnum)
        hexstr = hexstr[2:]
        if hexstr[-1] == 'L':
            hexstr = hexstr[0:-1]
        if len(hexstr) % 2:
            hexstr = '0' + hexstr
        upper = binascii.a2b_hex(hexstr)
        if len(upper) > len(prefix):
            return None
        return upper

    def __init__(self, indexes, fp):
        self._indexes = indexes
        self._fp = fp
        self._next_write_pos = fp.tell()

    def _write(self, flag, key, value, **kwargs):
        fp = self._fp
        pos = self._next_write_pos
        self._append(flag, key, value, fp, **kwargs)
        self._next_write_pos = fp.tell()
        logger.debug('Append journal entry.', flag=flag, key=key, value=value, pos=pos)
        return pos

    def _compact(self, src):
        dst_name = src.name + '.compacted'
        dst = open(dst_name, 'wb')
        self._truncate(dst, 0)
        for key in self._indexes:
            pos = self._indexes.get(key)
            value = self._read(pos, src)
            self._append(self.OP_SET, key, value, dst)
        return dst

    def close(self, sweep=False):
        if sweep:
            self.sweep()
        self._fp.close()
        self._indexes = None

    def close_and_remove(self):
        filename = self._fp.name
        self.close()
        try:
            os.remove(filename)
        except OSError:
            logger.exception('Delete checkpoint journal failed.')

    def sweep(self):
        src = self._fp
        src_name = src.name
        dst = self._compact(src)
        dst_name = dst.name
        src.close()
        dst.close()
        self._replace_file(dst_name, src_name)
        fp = open(src_name, 'a+b')
        indexes = self.build_indexes(fp)
        self._fp = fp
        self._indexes = indexes
        self._next_write_pos = fp.tell()

    def set(self, key, value, **kwargs):
        assert isinstance(key, (str, unicode))
        pos = self._write(self.OP_SET, key, value, **kwargs)
        self._indexes[key] = pos

    def get(self, key):
        item = self.find(key)
        if item is None:
            raise KeyError()
        return item.value

    def find(self, key):
        pos = self._indexes.get(key, None)
        if pos:
            value = self._read(pos, self._fp)
            return Item(key, value)
        return None

    def delete(self, key, **kwargs):
        pos = self._indexes.get(key, None)
        if pos:
            self._write(self.OP_DELETE, key, None, **kwargs)
            del self._indexes[key]

    def range(self, minimum=None, maximal=None, policy=(True, True), reverse=False):
        return self._indexes.irange(minimum, maximal, policy, reverse)

    def prefix(self, prefix, reverse=False):
        maximal = self.nearest_greater_prefix(prefix)
        query = (prefix, maximal, (True, False), reverse)
        for key in self.range(*query):
            if not key.startswith(prefix):
                break
            yield key

    def partition(self, prefix):
        return Partition(self, prefix)

    def flush(self):
        self._flush(self._fp)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


if __name__ == '__main__':
    print 'Convert binary checkpoint file to json file...'
    import sys
    import json
    if len(sys.argv) != 2:
        print 'Usage: \n\t' \
              '$SPLUNK_HOME/etc/apps/Splunk_TA_aws/bin/' \
              'splunksdc/checkpoint.py ' \
              '<file name of binary checkpoint>'
        sys.exit(0)


    def dump_data(data):
        import collections
        if isinstance(data, (basestring, int, long, float, bool)):
            return data
        elif isinstance(data, collections.Mapping):
            return dict(map(dump_data, data.iteritems()))
        elif isinstance(data, collections.Iterable):
            return map(dump_data, data)
        else:
            return str(data)

    ckpt = LocalKVStore.open_always(sys.argv[1])
    cont = {key: dump_data(ckpt.get(key)) for key in ckpt.range()}

    output_file = sys.argv[1] + '.json'
    with open(output_file, 'w') as f:
        f.write(json.dumps(cont, sort_keys=True))
    print 'Output into file: %s' % output_file
