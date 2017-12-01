"""
S3 checkpoint version 3, based on binary file kv store
"""

import os
import os.path as op

import splunktalib.common.util as scutil
import splunksdc.log as logging

import splunk_ta_aws.common.ta_aws_consts as tac
import aws_s3_consts as asc

from splunksdc import environ
from splunksdc.checkpoint import LocalKVStore

from splunk_ta_aws.common.checkpoint import LocalKVService

from .aws_s3_checkpointer_v2 import create_state_store
from .aws_s3_checkpointer_v2 import convert_legacy_ckpt_to_new_ckpts


logger = logging.get_module_logger()


def ckpt_file(ckpt_name, ckpt_dir):
    """
    Make full name of checkpoint.v3 file
    :param ckpt_name:
    :param ckpt_dir:
    :return:
    """
    ckpt_file_name = '%s.v3.ckpt' % ckpt_name
    return op.join(ckpt_dir, ckpt_file_name)


class S3CkptPool(object):
    """
    S3 Checkpoint Pool for every data input with binary file kv store
    """

    CKPT_POOL = {}

    CKPT_MEM_IDX = 'index'
    CKPT_MEM_KEY = 'key'

    class S3CkptItem(object):
        """
        S3 data input checkpoint item.
        :param ckpt_name: checkpoint name, data input name
        :param ckpt_dir: checkpoint storing directory

        Properties::
            >>> ckpt_item = S3CkptPool.S3CkptItem('ckpt_name', 'ckpt_dir')
            >>> ckpt_item.idx_ckpt # checkpoint for index
            >>> ckpt_item.key_ckpt # checkpoint for key
        """
        def __init__(self, ckpt_name, ckpt_dir):
            ckpt_file_idx, ckpt_file_key = map(
                ckpt_file,
                [ckpt_name+'.'+S3CkptPool.CKPT_MEM_IDX,
                 ckpt_name+'.'+S3CkptPool.CKPT_MEM_KEY],
                [ckpt_dir] * 2,
            )
            self.idx_ckpt = LocalKVStore.open_always(ckpt_file_idx)
            self.key_ckpt = LocalKVService.create(ckpt_file_key)

    @staticmethod
    def get(ckpt_name, ckpt_dir):
        """
        Get checkpoint item for S3 data input
        :param ckpt_name: checkpoint name, data input name
        :param ckpt_dir: checkpoint storing directory
        :return:
        """
        if ckpt_name not in S3CkptPool.CKPT_POOL:
            logger.info(
                'Open checkpoint.v3 item for S3 input.', ckpt_name=ckpt_name)
            S3CkptPool.CKPT_POOL[ckpt_name] = \
                S3CkptPool.S3CkptItem(ckpt_name, ckpt_dir)
        return S3CkptPool.CKPT_POOL[ckpt_name]

    @staticmethod
    def clean(ckpt_name):
        """
        Tear down checkpoint item for S3 data input
        :param ckpt_name:
        :return:
        """
        if ckpt_name in S3CkptPool.CKPT_POOL:
            logger.info(
                'Close checkpoint.v3 item for S3 input.', ckpt_name=ckpt_name)
            ckpt_item = S3CkptPool.CKPT_POOL[ckpt_name]
            ckpt_item.idx_ckpt.sweep()
            ckpt_item.key_ckpt.sweep()
            ckpt_item.idx_ckpt.close()
            ckpt_item.key_ckpt.close()
            del S3CkptPool.CKPT_POOL[ckpt_name]

    @staticmethod
    def close_all():
        """
        Tear down checkpoint items for all S3 data inputs
        :return:
        """
        for _, ckpt_item in S3CkptPool.CKPT_POOL.iteritems():
            ckpt_item.idx_ckpt.close()
            ckpt_item.key_ckpt.close()
        S3CkptPool.CKPT_POOL = {}

    @staticmethod
    def sweep_all():
        """
        Tear down checkpoint items for all S3 data inputs
        :return:
        """
        for _, ckpt_item in S3CkptPool.CKPT_POOL.iteritems():
            ckpt_item.idx_ckpt.sweep()
            ckpt_item.key_ckpt.sweep()

    @staticmethod
    def clean_and_remove(ckpt_name, ckpt_dir):
        """
        Tear down checkpoint item for S3 data input and remove it from disk
        :param ckpt_name:
        :return:
        """
        logger.info('Close and remove checkpoint.v3 item for S3 input.',
                    ckpt_name=ckpt_name)
        ckpt_item = S3CkptPool.get(ckpt_name, ckpt_dir)
        ckpt_item.idx_ckpt.close_and_remove()
        ckpt_item.key_ckpt.close_and_remove()
        del S3CkptPool.CKPT_POOL[ckpt_name]


class S3IndexCheckpointer(object):

    def __init__(self, config, new=True):
        self._config = config
        self._idx_ckpt = S3CkptPool.get(
            config[asc.data_input], config[tac.checkpoint_dir]
        ).idx_ckpt
        self._meta_fields = self._get_meta_fields(new)

    def _get_meta_fields(self, new):
        meta_fields = None
        try:
            meta_fields = self._idx_ckpt.get(asc.meta_fields)
            if asc.latest_scanned not in meta_fields:
                meta_fields[asc.latest_scanned] = ''
        except KeyError:
            logger.info('Index checkpoint.v3 for S3 data input does not exist')
            if new:
                last_modified = self._config.get(asc.last_modified)
                meta_fields = {
                    asc.latest_last_modified: last_modified,
                    asc.latest_scanned: '',
                    asc.bucket_name: self._config[asc.bucket_name],
                    asc.version: 3,
                }
                self._idx_ckpt.set(asc.meta_fields, meta_fields)
                logger.info('Create checkpoint.v3 for S3 data input.')
        return meta_fields

    def _reform_item(self, key):
        return {
            asc.last_modified: self._idx_ckpt.get(key).get(asc.last_modified),
        }

    def keys(self):
        """
        Get S3 keys exist in index
        :return:
        """
        self.save()
        for key in self._idx_ckpt.range():
            if key == asc.meta_fields:
                continue
            yield key

    def add(self, key_name, last_modified, flush=True):
        index_entry = {
            asc.last_modified: last_modified,
        }
        self._idx_ckpt.set(key_name, index_entry, flush=flush)

    def get(self, key_name):
        return self._idx_ckpt.get(key_name)

    def delete_item(self, key_name, commit=True):
        self._idx_ckpt.delete(key_name)

    def bucket_name(self):
        return self._meta_fields[asc.bucket_name]

    def last_modified(self):
        return self._meta_fields[asc.latest_last_modified]

    def set_last_modified(self, last_modified, commit=True):
        self._meta_fields[asc.latest_last_modified] = last_modified
        if commit:
            self.save()

    def latest_scanned(self):
        return self._meta_fields[asc.latest_scanned]

    def set_latest_scanned(self, latest_scanned):
        self._meta_fields[asc.latest_scanned] = latest_scanned
        self.save()

    @scutil.retry(retries=3, reraise=True, logger=logger)
    def save(self):
        """
        Save meta fields for index checkpoint
        :return:
        """
        self._idx_ckpt.set(asc.meta_fields, self._meta_fields)

    @scutil.retry(retries=3, reraise=True, logger=logger)
    def get_state(self, key):
        """
        Get S3 key
        Generic get, proxy for StateStore
        """
        key_ckpt = S3CkptPool.get(
            self._config[asc.data_input],
            self._config[tac.checkpoint_dir],
        ).key_ckpt
        try:
            return key_ckpt.get(key)
        except KeyError:
            return None

    def delete_state(self, key):
        """
        Delete S3 key
        Generic delete, proxy for StateStore
        """
        ckpt_key = S3CkptPool.get(
            self._config[asc.data_input],
            self._config[tac.checkpoint_dir],
        ).key_ckpt
        ckpt_key.delete(key)

    def delete(self):
        self._idx_ckpt.close_and_remove(self._config[asc.data_input])
        logger.debug("Remove checkpoint.v3")

    def flush(self):
        ckpt = S3CkptPool.get(
            self._config[asc.data_input],
            self._config[tac.checkpoint_dir],
        )
        ckpt.key_ckpt.flush()
        ckpt.idx_ckpt.flush()


class S3KeyCheckpointer(object):

    def __init__(self, config, key):
        self._config = config
        self._key_name = key.name
        self._key_ckpt = S3CkptPool.get(
            config[asc.data_input],
            config[tac.checkpoint_dir],
        ).key_ckpt
        self._is_new = False
        self._key_item = self._pop_ckpt_item(key)

    def _pop_ckpt_item(self, key):
        try:
            key_item = self._key_ckpt.get(self._key_name)
        except KeyError:
            logger.debug(
                'Create checkpoint.v3 item for S3!', key=self._key_name)
            self._is_new = True
            key_item = {
                asc.etag: key.etag,
                asc.last_modified: key.last_modified,
                asc.offset: 0,
                asc.eof: False,
                asc.error_count: 0,
                asc.encoding: None,
                asc.state: asc.new,
                asc.version: 3,
            }
        return key_item

    @property
    def is_new(self):
        return self._is_new

    def ckpt_key(self):
        return self._key_item

    def encoding(self):
        return self._key_item[asc.encoding]

    def set_encoding(self, encoding, commit=True):
        self._key_item[asc.encoding] = encoding
        if commit:
            self.save()

    def data_input(self):
        return self._key_item[asc.data_input]

    def etag(self):
        return self._key_item[asc.etag]

    def last_modified(self):
        return self._key_item[asc.last_modified]

    def eof(self):
        return self._key_item[asc.eof]

    def set_eof(self, eof, commit=True):
        self._key_item[asc.eof] = eof
        if commit:
            self.save()

    def offset(self):
        return self._key_item[asc.offset]

    def increase_offset(self, increment, commit=True):
        self._key_item[asc.offset] += increment
        if commit:
            self.save()

    def increase_error_count(self, count=1, commit=True):
        self._key_item[asc.error_count] += count
        self._key_item[asc.state] = asc.failed
        if commit:
            self.save()

    def error_count(self):
        return self._key_item[asc.error_count]

    def set_offset(self, offset, commit=True):
        self._key_item[asc.offset] = offset
        if commit:
            self.save()

    def set_state(self, state, flush=True):
        self._key_item[asc.state] = state
        self._key_ckpt.set(self._key_name, self._key_item, flush=flush)

    def state(self):
        return self._key_item[asc.state]

    @scutil.retry(retries=3, reraise=True, logger=logger)
    def save(self):
        self._key_ckpt.set(self._key_name, self._key_item)

    def delete(self):
        self._key_ckpt.delete(self._key_name)


def convert_state_store_to_bin_kv_store(tasks):
    """
    Convert checkpoint from state store to binary file kv store (v2 to v3).
    :return:
    """
    store = create_state_store(tasks[0])

    # checkpoint for every data input
    for task in tasks:
        ckpt_v2_idx_key = task[asc.data_input] + '.ckpt'
        idx_ckpt_v2 = store.get_state(ckpt_v2_idx_key)
        if not idx_ckpt_v2:
            continue

        # backup old index ckpt before converting
        ckpt_v2_idx_key_bak = task[asc.data_input] + '.ckpt.bak'
        store.update_state(ckpt_v2_idx_key_bak, idx_ckpt_v2)

        ckpt_item_v3 = S3CkptPool.get(
            task[asc.data_input], task[tac.checkpoint_dir]
        )
        meta_fields = {
            asc.latest_last_modified: task[asc.last_modified],
            asc.bucket_name: task[asc.bucket_name],
            asc.version: 3,
        }
        ckpt_item_v3.idx_ckpt.set(asc.meta_fields, meta_fields)
        for name, item in idx_ckpt_v2[asc.keys].iteritems():
            key_ckpt = item[asc.key_ckpt]
            del item[asc.key_ckpt]
            ckpt_item_v3.idx_ckpt.set(name, item)

            key_ckpt_item = store.get_state(key_ckpt)
            if key_ckpt_item:
                key_ckpt_item[asc.version] = 3
                ckpt_item_v3.key_ckpt.set(name, key_ckpt_item)
        S3CkptPool.clean(task[asc.data_input])
        store.delete_state(ckpt_v2_idx_key)


def handle_ckpts(tasks):
    """
    Convert all legacy ckpts to binary file kv_store (all v1 and v2 to v3)
    """

    if not tasks:
        return

    convert_legacy_ckpt_to_new_ckpts(tasks)
    convert_state_store_to_bin_kv_store(tasks)


def delete_ckpt(input_name):
    ckpt_dir = environ.get_checkpoint_folder('aws_s3')
    ckpt_idx = ckpt_file(input_name+'.'+S3CkptPool.CKPT_MEM_IDX, ckpt_dir)
    ckpt_key = ckpt_file(input_name+'.'+S3CkptPool.CKPT_MEM_KEY, ckpt_dir)

    # try remove files for index & key
    if op.isfile(ckpt_idx):
        os.remove(ckpt_idx)
    if op.isfile(ckpt_key):
        os.remove(ckpt_key)
    logger.info('Checkpoint files are deleted.', input=input_name,
                index_file=ckpt_idx, key_file=ckpt_key)
