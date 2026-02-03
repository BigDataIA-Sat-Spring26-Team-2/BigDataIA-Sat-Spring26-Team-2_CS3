# app/services/s3_storage.py
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import mimetypes

import boto3
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError
import structlog

from app.config import get_settings

logger = structlog.get_logger()


@lru_cache
def _s3_client():
    """
    Cached S3 client using explicit credentials from Settings.
    """
    s = get_settings()
    session = boto3.session.Session(
        aws_access_key_id=s.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=s.AWS_SECRET_ACCESS_KEY,
        region_name=s.AWS_REGION,
    )
    return session.client("s3")


def s3_object_exists(bucket: str, key: str) -> bool:
    """
    True if s3://bucket/key exists, else False.
    Raises for non-404 S3 errors (auth/permissions/etc).
    """
    s3 = _s3_client()
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey", "NotFound"):
            return False
        raise


async def check_s3() -> str:
    """
    Health check for S3. Returns:
    - "healthy" if bucket is accessible
    - "not_configured" if env vars missing
    - "unhealthy" otherwise
    """
    try:
        s = get_settings()
        if not all([s.AWS_ACCESS_KEY_ID, s.AWS_SECRET_ACCESS_KEY, s.S3_BUCKET]):
            return "not_configured"

        s3 = _s3_client()
        s3.head_bucket(Bucket=s.S3_BUCKET)
        return "healthy"

    except (NoCredentialsError, PartialCredentialsError):
        return "not_configured"
    except ClientError:
        return "unhealthy"
    except Exception:
        return "unhealthy"


def upload_file_to_s3(local_path: Path, s3_key: str) -> str:
    """
    Upload a local file into S3 and return s3:// uri.
    """
    s = get_settings()
    s3 = _s3_client()

    content_type, _ = mimetypes.guess_type(str(local_path))
    extra_args = {}
    if content_type:
        extra_args["ContentType"] = content_type

    logger.info(
        "s3_upload_started",
        local_path=str(local_path),
        s3_key=s3_key,
        bucket=s.S3_BUCKET,
    )

    try:
        if extra_args:
            s3.upload_file(
                Filename=str(local_path),
                Bucket=s.S3_BUCKET,
                Key=s3_key,
                ExtraArgs=extra_args,
            )
        else:
            s3.upload_file(
                Filename=str(local_path),
                Bucket=s.S3_BUCKET,
                Key=s3_key,
            )
    except Exception as e:
        logger.exception("s3_upload_failed", s3_key=s3_key, error=str(e))
        raise

    s3_uri = f"s3://{s.S3_BUCKET}/{s3_key}"

    logger.info(
        "s3_upload_completed",
        s3_uri=s3_uri,
        file_size_bytes=local_path.stat().st_size,
    )

    return s3_uri
