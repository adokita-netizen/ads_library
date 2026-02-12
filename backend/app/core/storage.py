"""MinIO/S3 object storage client."""

import io
from typing import Optional

from minio import Minio
from minio.error import S3Error

from app.core.config import get_settings

settings = get_settings()


class StorageClient:
    """S3-compatible object storage client using MinIO."""

    def __init__(self):
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_use_ssl,
        )
        self.bucket_name = settings.minio_bucket_name
        self._ensure_bucket()

    def _ensure_bucket(self):
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
        except S3Error:
            pass

    def upload_file(self, object_name: str, file_path: str, content_type: str = "application/octet-stream") -> str:
        self.client.fput_object(
            self.bucket_name,
            object_name,
            file_path,
            content_type=content_type,
        )
        return f"{self.bucket_name}/{object_name}"

    def upload_bytes(self, object_name: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        self.client.put_object(
            self.bucket_name,
            object_name,
            io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        return f"{self.bucket_name}/{object_name}"

    def download_file(self, object_name: str, file_path: str):
        self.client.fget_object(self.bucket_name, object_name, file_path)

    def get_bytes(self, object_name: str) -> bytes:
        response = self.client.get_object(self.bucket_name, object_name)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def get_presigned_url(self, object_name: str, expires: int = 3600) -> str:
        from datetime import timedelta
        return self.client.presigned_get_object(
            self.bucket_name,
            object_name,
            expires=timedelta(seconds=expires),
        )

    def delete_file(self, object_name: str):
        self.client.remove_object(self.bucket_name, object_name)

    def list_objects(self, prefix: str = "", recursive: bool = True) -> list:
        objects = self.client.list_objects(
            self.bucket_name, prefix=prefix, recursive=recursive
        )
        return [obj.object_name for obj in objects]


_storage_client: Optional[StorageClient] = None


def get_storage_client() -> StorageClient:
    global _storage_client
    if _storage_client is None:
        _storage_client = StorageClient()
    return _storage_client
