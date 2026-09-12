from functools import lru_cache

from app.core.config import settings
from app.storage.base import StorageBackend
from app.storage.local import LocalDiskStorage


@lru_cache
def get_storage() -> StorageBackend:
    # ponytail: only "local" is implemented. To add real object storage, write an
    # S3Storage(StorageBackend) using boto3 and branch on settings.storage_backend
    # here -- nothing outside this function needs to change.
    if settings.storage_backend == "local":
        return LocalDiskStorage(settings.upload_dir)
    raise ValueError(f"Unknown storage backend: {settings.storage_backend}")


__all__ = ["StorageBackend", "get_storage"]
