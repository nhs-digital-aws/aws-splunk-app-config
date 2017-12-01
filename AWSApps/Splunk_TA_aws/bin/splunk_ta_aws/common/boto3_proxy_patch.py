import botocore.endpoint


HTTP_PROXY = None
HTTPS_PROXY = None


def _get_proxies(self, url):
    return {"http": HTTP_PROXY, "https": HTTPS_PROXY}

botocore.endpoint.EndpointCreator._get_proxies = _get_proxies


def set_proxies(http_proxy, https_proxy):
    global HTTP_PROXY
    global HTTPS_PROXY

    HTTP_PROXY = http_proxy
    HTTPS_PROXY = https_proxy
