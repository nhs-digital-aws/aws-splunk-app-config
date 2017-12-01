import threading
import splunktalib.orphan_process_monitor as opm
from splunk_ta_aws.common.s3util import create_s3_connection_from_keyname

# Event writer
event_writer = None


def create_s3_connection(bucket_name, key_name,
                         key_id, secret_key, session_key):
    region_rex = r"\d+_CloudTrail_([\w-]+)_\d{4}\d{2}\d{2}T\d{2}\d{2}Z_.{16}" \
                 r"\.json\.gz$"
    return create_s3_connection_from_keyname(
        key_id, secret_key, session_key, bucket_name, key_name, region_rex)


_orphan_checker = opm.OrphanProcessChecker()


def orphan_check():
    """
    Check if this is orphan process.
    :return:
    """
    if _orphan_checker.is_orphan():
        raise InputCancellationError(
            'Input was stop. This is an orphan process.')


class InputCancellationError(Exception):
    """
    Input was stop. This is an orphan process.
    """
    pass


class CloudTrailProcessorError(Exception):
    """
    AWS CloudTrail notifications processing error.
    """
    pass


class ThreadLocalSingleton(type):
    """
    Thread-local singleton: only one instance of a given class per thread.
    """

    _local = threading.local()

    def __call__(cls, *args, **kwargs):
        try:
            return getattr(ThreadLocalSingleton._local, cls.__name__)
        except AttributeError:
            instance = super(ThreadLocalSingleton, cls).__call__()
            setattr(ThreadLocalSingleton._local, cls.__name__, instance)
            return instance
