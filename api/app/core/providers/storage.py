"""Object storage: R2 in deployed environments, MinIO locally (D-027, T-4.1).

Browsers upload and download through presigned URLs only; the server reads and
writes bytes directly (re-encoding, watermarking).
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any, Protocol

import aioboto3  # type: ignore[import-untyped]
from botocore.config import Config  # type: ignore[import-untyped]
from botocore.exceptions import ClientError  # type: ignore[import-untyped]

from app.core.config import STORAGE_ENDPOINT_OVERRIDE_ALLOWED_IN, Settings


class ObjectNotFound(Exception):
    """No object at that bucket and key."""


@dataclass(frozen=True)
class PresignedPut:
    url: str
    headers: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ObjectInfo:
    size: int
    content_type: str


class StorageProvider(Protocol):
    # D-027: presigned PUTs last 5 minutes and GETs 10.
    async def presign_put(
        self, bucket: str, key: str, content_type: str, max_bytes: int, ttl: int = 300
    ) -> PresignedPut:
        """A URL the browser PUTs one object to, with exactly `content_type`.

        A presigned PUT can't cap its own size, so `max_bytes` is the caller's
        to check with `head()` once the upload says it's done (T-4.2)."""
        ...

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

    async def head(self, bucket: str, key: str) -> ObjectInfo:
        """The object's size and type; raises `ObjectNotFound` if there is none."""
        ...

    async def aclose(self) -> None:
        """Release connections. Safe to call more than once."""
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

    async def head(self, bucket: str, key: str) -> ObjectInfo:
        stored = self._get(bucket, key)
        return ObjectInfo(size=len(stored.data), content_type=stored.content_type)

    async def aclose(self) -> None:
        return None

    def _get(self, bucket: str, key: str) -> StoredObject:
        try:
            return self.objects[(bucket, key)]
        except KeyError:
            raise ObjectNotFound(f"{bucket}/{key}") from None


def storage_endpoint(settings: Settings) -> str:
    """R2's own endpoint for this account, unless `ENV` is one where
    `R2_ENDPOINT_URL` may point elsewhere (MinIO): an allowlist (rule 16), so
    no setting can send photos to another S3 anywhere else. `Settings` refuses
    the override there too; this holds even for settings it never checked."""
    if (
        settings.R2_ENDPOINT_URL
        and settings.ENV in STORAGE_ENDPOINT_OVERRIDE_ALLOWED_IN
    ):
        return settings.R2_ENDPOINT_URL
    return f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"


# S3's codes for "no such object": GET's and COPY's carry a body, HEAD's doesn't.
_NOT_FOUND = frozenset({"NoSuchKey", "404", "NotFound"})


class S3Storage:
    """aioboto3 against R2, or MinIO locally.

    One client per app, opened at first use and kept, so calls reuse its
    connections; `aclose()` releases it. Path-style addressing, so every bucket
    is on one host: R2's endpoint, which T-4.6's CSP names once.
    """

    def __init__(self, settings: Settings) -> None:
        self._endpoint = storage_endpoint(settings)
        self._key_id = settings.R2_ACCESS_KEY_ID
        self._secret = settings.R2_SECRET_ACCESS_KEY
        self._session = aioboto3.Session()
        self._client: Any = None
        self._stack: AsyncExitStack | None = None
        self._opening = asyncio.Lock()

    async def _s3(self) -> Any:
        if self._client is None:
            async with self._opening:
                if self._client is None:
                    stack = AsyncExitStack()
                    self._client = await stack.enter_async_context(
                        self._session.client(
                            "s3",
                            endpoint_url=self._endpoint,
                            aws_access_key_id=self._key_id,
                            aws_secret_access_key=self._secret,
                            # R2's region; MinIO accepts it too.
                            region_name="auto",
                            config=Config(
                                signature_version="s3v4",
                                s3={"addressing_style": "path"},
                            ),
                        )
                    )
                    self._stack = stack
        return self._client

    async def aclose(self) -> None:
        stack, self._stack, self._client = self._stack, None, None
        if stack is not None:
            await stack.aclose()

    async def presign_put(
        self, bucket: str, key: str, content_type: str, max_bytes: int, ttl: int = 300
    ) -> PresignedPut:
        s3 = await self._s3()
        url: str = await s3.generate_presigned_url(
            "put_object",
            Params={"Bucket": bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=ttl,
        )
        return PresignedPut(url=url, headers={"Content-Type": content_type})

    async def presign_get(self, bucket: str, key: str, ttl: int = 600) -> str:
        s3 = await self._s3()
        url: str = await s3.generate_presigned_url(
            "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=ttl
        )
        return url

    async def get_bytes(self, bucket: str, key: str) -> bytes:
        s3 = await self._s3()
        try:
            response = await s3.get_object(Bucket=bucket, Key=key)
        except ClientError as error:
            raise _not_found_or(error, bucket, key) from None
        async with response["Body"] as body:
            data: bytes = await body.read()
        return data

    async def put_bytes(
        self, bucket: str, key: str, data: bytes, content_type: str
    ) -> None:
        s3 = await self._s3()
        await s3.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)

    async def copy(
        self, src_bucket: str, src_key: str, dst_bucket: str, dst_key: str
    ) -> None:
        s3 = await self._s3()
        try:
            await s3.copy_object(
                CopySource={"Bucket": src_bucket, "Key": src_key},
                Bucket=dst_bucket,
                Key=dst_key,
            )
        except ClientError as error:
            raise _not_found_or(error, src_bucket, src_key) from None

    async def delete(self, bucket: str, key: str) -> None:
        s3 = await self._s3()
        await s3.delete_object(Bucket=bucket, Key=key)

    async def head(self, bucket: str, key: str) -> ObjectInfo:
        s3 = await self._s3()
        try:
            response = await s3.head_object(Bucket=bucket, Key=key)
        except ClientError as error:
            raise _not_found_or(error, bucket, key) from None
        return ObjectInfo(
            size=int(response["ContentLength"]),
            content_type=str(response.get("ContentType", "")),
        )


def _not_found_or(error: Any, bucket: str, key: str) -> Exception:
    """`ObjectNotFound` for S3's "no such object", else the error itself."""
    if error.response.get("Error", {}).get("Code") in _NOT_FOUND:
        return ObjectNotFound(f"{bucket}/{key}")
    exception: Exception = error
    return exception
