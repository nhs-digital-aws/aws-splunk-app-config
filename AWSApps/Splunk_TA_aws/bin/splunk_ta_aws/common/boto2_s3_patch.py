from boto.s3.connection import S3Connection


class RegionRedirection(Exception):
    def __init__(self, region_name):
        self.region_name = region_name


def make_request_wrapper(func):
    def wrapper(*args, **kwargs):
        response = func(*args, **kwargs)
        if response.status == 301 and args[1] == 'HEAD':
            headers = response.getheaders()
            for key, value in headers:
                if key == "x-amz-bucket-region":
                    raise RegionRedirection(value)
        return response
    return wrapper

S3Connection.make_request = make_request_wrapper(S3Connection.make_request)
