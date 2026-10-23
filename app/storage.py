import asyncio
import uuid
from pathlib import Path, PurePosixPath

import boto3

from app.config import get_settings


def make_storage_key(filename: str) -> str:
    return f"documents/{uuid.uuid4().hex}{Path(filename).suffix.lower()}"


def _client():
    s = get_settings()
    return boto3.client("s3", endpoint_url=s.s3_endpoint_url, region_name=s.s3_region,
                        aws_access_key_id=s.s3_access_key_id, aws_secret_access_key=s.s3_secret_access_key)


async def put_bytes(key: str, content: bytes, content_type: str) -> None:
    s = get_settings()
    if s.object_storage_enabled:
        await asyncio.to_thread(_client().put_object, Bucket=s.s3_bucket, Key=key, Body=content, ContentType=content_type)
        return
    if s.dezny_env.lower() == "production":
        raise RuntimeError("Object storage must be configured in production; local storage is not durable.")
    root = s.local_storage_dir.resolve()
    target = (root / PurePosixPath(key)).resolve()
    if root not in target.parents:
        raise ValueError("Invalid storage key")
    target.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(target.write_bytes, content)


async def get_bytes(key: str) -> bytes:
    s = get_settings()
    if s.object_storage_enabled:
        result = await asyncio.to_thread(_client().get_object, Bucket=s.s3_bucket, Key=key)
        return await asyncio.to_thread(result["Body"].read)
    if s.dezny_env.lower() == "production":
        raise RuntimeError("Object storage must be configured in production; local storage is not durable.")
    root = s.local_storage_dir.resolve()
    target = (root / PurePosixPath(key)).resolve()
    if root not in target.parents:
        raise ValueError("Invalid storage key")
    return await asyncio.to_thread(target.read_bytes)
