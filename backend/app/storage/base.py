from abc import ABC, abstractmethod


class StorageBackend(ABC):
    """S3-compatible storage seam. Any implementation (local disk, S3, R2, MinIO)
    just needs to satisfy this interface -- callers never touch paths/URLs directly.
    """

    @abstractmethod
    def save(self, content: bytes, storage_key: str) -> None: ...

    @abstractmethod
    def read(self, storage_key: str) -> bytes: ...

    @abstractmethod
    def delete(self, storage_key: str) -> None: ...
