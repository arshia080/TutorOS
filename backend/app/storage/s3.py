import boto3
from botocore.exceptions import ClientError

from app.storage.base import StorageBackend


class S3Storage(StorageBackend):
    """S3-compatible implementation (works against real AWS S3/R2 or an
    S3-compatible endpoint like the MinIO container in docker-compose.yml --
    just set s3_endpoint_url to None for real AWS).
    """

    def __init__(self, bucket: str, endpoint_url: str | None, access_key: str, secret_key: str, region: str):
        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError:
            self.client.create_bucket(Bucket=self.bucket)

    def save(self, content: bytes, storage_key: str) -> None:
        self.client.put_object(Bucket=self.bucket, Key=storage_key, Body=content)

    def read(self, storage_key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=storage_key)["Body"].read()

    def delete(self, storage_key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=storage_key)
