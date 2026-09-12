from pathlib import Path

from app.storage.base import StorageBackend


class LocalDiskStorage(StorageBackend):
    """Dev-only implementation. storage_key is always a randomly generated name
    (see app/services/upload_service.py) so it's safe to use directly as a path
    component -- it never comes from client input.
    """

    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, content: bytes, storage_key: str) -> None:
        (self.base_dir / storage_key).write_bytes(content)

    def read(self, storage_key: str) -> bytes:
        return (self.base_dir / storage_key).read_bytes()

    def delete(self, storage_key: str) -> None:
        path = self.base_dir / storage_key
        if path.exists():
            path.unlink()
