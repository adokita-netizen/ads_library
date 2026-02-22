"""Object storage client with MinIO (local) and S3 (AWS) backends."""

import io
from abc import ABC, abstractmethod
from typing import Optional

from app.core.config import get_settings

settings = get_settings()


class BaseStorageClient(ABC):
    """Abstract storage client interface."""

    @abstractmethod
    def upload_file(self, object_name: str, file_path: str, content_type: str = "application/octet-stream") -> str: ...

    @abstractmethod
    def upload_bytes(self, object_name: str, data: bytes, content_type: str = "application/octet-stream") -> str: ...

    @abstractmethod
    def download_file(self, object_name: str, file_path: str): ...

    @abstractmethod
    def get_bytes(self, object_name: str) -> bytes: ...

    @abstractmethod
    def get_presigned_url(self, object_name: str, expires: int = 3600) -> str: ...

    @abstractmethod
    def delete_file(self, object_name: str): ...

    @abstractmethod
    def list_objects(self, prefix: str = "", recursive: bool = True) -> list: ...


class MinIOStorageClient(BaseStorageClient):
    """S3-compatible object storage client using MinIO (local development)."""

    def __init__(self):
        from minio import Minio

        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_use_ssl,
        )
        self.bucket_name = settings.minio_bucket_name
        self._ensure_bucket()

    def _ensure_bucket(self):
        from minio.error import S3Error
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


class S3StorageClient(BaseStorageClient):
    """AWS S3 storage client (production)."""

    def __init__(self):
        import boto3
        self.s3 = boto3.client("s3", region_name=settings.aws_region)
        self.bucket_name = settings.aws_s3_bucket

    def upload_file(self, object_name: str, file_path: str, content_type: str = "application/octet-stream") -> str:
        self.s3.upload_file(
            file_path,
            self.bucket_name,
            object_name,
            ExtraArgs={"ContentType": content_type},
        )
        return f"{self.bucket_name}/{object_name}"

    def upload_bytes(self, object_name: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        self.s3.put_object(
            Bucket=self.bucket_name,
            Key=object_name,
            Body=data,
            ContentType=content_type,
        )
        return f"{self.bucket_name}/{object_name}"

    def download_file(self, object_name: str, file_path: str):
        self.s3.download_file(self.bucket_name, object_name, file_path)

    def get_bytes(self, object_name: str) -> bytes:
        response = self.s3.get_object(Bucket=self.bucket_name, Key=object_name)
        return response["Body"].read()

    def get_presigned_url(self, object_name: str, expires: int = 3600) -> str:
        return self.s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket_name, "Key": object_name},
            ExpiresIn=expires,
        )

    def delete_file(self, object_name: str):
        self.s3.delete_object(Bucket=self.bucket_name, Key=object_name)

    def list_objects(self, prefix: str = "", recursive: bool = True) -> list:
        paginator = self.s3.get_paginator("list_objects_v2")
        names = []
        for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
            for obj in page.get("Contents", []):
                names.append(obj["Key"])
        return names


# Backward-compatible alias
StorageClient = BaseStorageClient

_storage_client: Optional[BaseStorageClient] = None


def get_storage_client() -> BaseStorageClient:
    global _storage_client
    if _storage_client is None:
        if settings.storage_backend == "s3":
            _storage_client = S3StorageClient()
        else:
            _storage_client = MinIOStorageClient()
    return _storage_client
