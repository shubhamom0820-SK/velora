"""Object storage: R2 in deployed environments, MinIO locally (D-027, T-4.1).

Browsers upload and download through presigned URLs only; the server reads and
writes bytes directly (re-encoding, watermarking).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol


class ObjectNotFound(Exception):
    """No object at that bucket and key."""


@dataclass(frozen=True)
class PresignedPut:
    url: str
    headers: Mapping[str, str] = field(default_factory=dict)


class StorageProvider(Protocol):
    # D-027: presigned PUTs last 5 minutes and GETs 10.
    async def presign_put(
        self, bucket: str, key: str, content_type: str, max_bytes: int, ttl: int = 300
    ) -> PresignedPut: ...

    async def presign_get(self, bucket: str, key: str, ttl: int = 600) -> str: ...

    async def get_bytes(self, bucket: str, key: str) -> bytes:
        """The object's bytes; raises `ObjectNotFound` if there is none."""
        ...

    async def put_bytes(
        self, bucket: str, key: str, data: bytes, content_type: str
    ) -> None: ...

    async def copy(
        self, src_bucket: str, src_key: str, dst_bucket: str, dst_key: str
    ) -> None:
        """Raises `ObjectNotFound` if the source doesn't exist."""
        ...

    async def delete(self, bucket: str, key: str) -> None:
        """Deleting an object that doesn't exist is not an error."""
        ...


@dataclass(frozen=True)
class StoredObject:
    data: bytes
    content_type: str


class FakeStorage:
    """Buckets in memory. Presigned URLs are `fake-storage://` links that go nowhere."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], StoredObject] = {}

    async def presign_put(
        self, bucket: str, key: str, content_type: str, max_bytes: int, ttl: int = 300
    ) -> PresignedPut:
        return PresignedPut(
            url=f"fake-storage://{bucket}/{key}?method=PUT&ttl={ttl}&max_bytes={max_bytes}",
            headers={"Content-Type": content_type},
        )

    async def presign_get(self, bucket: str, key: str, ttl: int = 600) -> str:
        return f"fake-storage://{bucket}/{key}?method=GET&ttl={ttl}"

    async def get_bytes(self, bucket: str, key: str) -> bytes:
        return self._get(bucket, key).data

    async def put_bytes(
        self, bucket: str, key: str, data: bytes, content_type: str
    ) -> None:
        self.objects[(bucket, key)] = StoredObject(data, content_type)

    async def copy(
        self, src_bucket: str, src_key: str, dst_bucket: str, dst_key: str
    ) -> None:
        self.objects[(dst_bucket, dst_key)] = self._get(src_bucket, src_key)

    async def delete(self, bucket: str, key: str) -> None:
        self.objects.pop((bucket, key), None)

    def _get(self, bucket: str, key: str) -> StoredObject:
        try:
            return self.objects[(bucket, key)]
        except KeyError:
            raise ObjectNotFound(f"{bucket}/{key}") from None


class S3Storage:
    """aioboto3 against R2, or MinIO locally. Not built yet."""

    async def presign_put(
        self, bucket: str, key: str, content_type: str, max_bytes: int, ttl: int = 300
    ) -> PresignedPut:
        raise NotImplementedError("S3 storage arrives with T-4.1.")

    async def presign_get(self, bucket: str, key: str, ttl: int = 600) -> str:
        raise NotImplementedError("S3 storage arrives with T-4.1.")

    async def get_bytes(self, bucket: str, key: str) -> bytes:
        raise NotImplementedError("S3 storage arrives with T-4.1.")

    async def put_bytes(
        self, bucket: str, key: str, data: bytes, content_type: str
    ) -> None:
        raise NotImplementedError("S3 storage arrives with T-4.1.")

    async def copy(
        self, src_bucket: str, src_key: str, dst_bucket: str, dst_key: str
    ) -> None:
        raise NotImplementedError("S3 storage arrives with T-4.1.")

    async def delete(self, bucket: str, key: str) -> None:
        raise NotImplementedError("S3 storage arrives with T-4.1.")
