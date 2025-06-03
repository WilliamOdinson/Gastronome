import urllib3
from django.conf import settings
from opensearchpy import OpenSearch

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def get_opensearch_client(timeout=10) -> OpenSearch:
    """
    Return a shared OpenSearch client based on Django settings.
    """
    return OpenSearch(
        hosts=[settings.OPENSEARCH["HOST"]],
        http_auth=(settings.OPENSEARCH["USER"], settings.OPENSEARCH["PASSWORD"]),
        verify_certs=False,
        retry_on_timeout=True,
        timeout=timeout,
    )
