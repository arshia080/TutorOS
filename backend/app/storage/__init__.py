from functools import lru_cache

from app.core.config import settings
from app.storage.base import StorageBackend
from app.storage.local import LocalDiskStorage


@lru_cache
def get_storage() -> StorageBackend:
    if settings.storage_backend == "local":
        return LocalDiskStorage(settings.upload_dir)
    if settings.storage_backend == "s3":
        from app.storage.s3 import S3Storage

        return S3Storage(
            bucket=settings.s3_bucket,
            endpoint_url=settings.s3_endpoint_url,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            region=settings.s3_region,
        )
    raise ValueError(f"Unknown storage backend: {settings.storage_backend}")


__all__ = ["StorageBackend", "get_storage"]
