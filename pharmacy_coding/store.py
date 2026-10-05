"""Pipeline outputs, kept in Azure Blob Storage so the pipeline and the review app share them.

Everything lives in the prototype-docs container under output/<folder>/<name>.json.
"""
import json
from functools import lru_cache

from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import ContainerClient

from . import config

CONTAINER = "prototype-docs"
PREFIX = "output/"


@lru_cache(maxsize=1)
def _container():
    return ContainerClient.from_connection_string(config.setting("AZURE_STORAGE_CONNECTION_STRING"), CONTAINER)


def write_json(path, data):
    _container().upload_blob(PREFIX + path, json.dumps(data, indent=1), overwrite=True)


def read_json(path, default=None):
    """Return the stored JSON, or default when the blob does not exist."""
    try:
        return json.loads(_container().download_blob(PREFIX + path).readall())
    except ResourceNotFoundError:
        return default


def names(folder):
    """Names (without .json) of everything stored directly in a folder."""
    prefix = f"{PREFIX}{folder}/"
    return sorted(blob.name[len(prefix):-len(".json")] for blob in _container().list_blobs(name_starts_with=prefix)
                  if blob.name.endswith(".json") and "/" not in blob.name[len(prefix):])
