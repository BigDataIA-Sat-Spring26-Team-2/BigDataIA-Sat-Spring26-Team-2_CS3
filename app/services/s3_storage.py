# app/services/s3_storage.py
import boto3
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError
from app.config import get_settings
import structlog    
from pathlib import Path

logger = structlog.get_logger()

async def check_s3() -> str:
    """
    Health check for S3.
    Fails if credentials in .env are invalid.
    """
    try:
        settings = get_settings()
        print("S3 DEBUG CREDS:", settings.AWS_ACCESS_KEY_ID)
        # Validate config exists
        if not all([
            settings.AWS_ACCESS_KEY_ID,
            settings.AWS_SECRET_ACCESS_KEY,
            settings.S3_BUCKET,
        ]):
            return "not_configured"

        # Force boto3 to use ONLY these credentials
        session = boto3.session.Session(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )

        s3_client = session.client("s3")

        # Make an auth-required call
        # head_bucket ALWAYS fails on bad creds
        s3_client.head_bucket(Bucket=settings.S3_BUCKET)

        return "healthy"

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        
        # These indicate bad credentials or access
        if error_code in ["403", "AccessDenied", "InvalidAccessKeyId", "SignatureDoesNotMatch"]:
            return "unhealthy"

        return "unhealthy"

    except (NoCredentialsError, PartialCredentialsError):
        return "not_configured"

    except Exception:
        return "unhealthy"


def upload_file_to_s3(
    local_path: Path,
    s3_key: str,
) -> str:
    try:
        settings = get_settings()

        session = boto3.session.Session(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )

        s3_client = session.client("s3")

        logger.info(
            "s3_upload_started",
            local_path=str(local_path),
            s3_key=s3_key,
            bucket=settings.S3_BUCKET,
        )

        s3_client.upload_file(
            Filename=str(local_path),
            Bucket=settings.S3_BUCKET,
            Key=s3_key,
        )

        s3_uri = f"s3://{settings.S3_BUCKET}/{s3_key}"

        logger.info(
            "s3_upload_completed",
            s3_uri=s3_uri,
            file_size_bytes=local_path.stat().st_size,
        )

        return s3_uri

    except ClientError as e:
        logger.error(
            "s3_upload_failed",
            local_path=str(local_path),
            s3_key=s3_key,
            error_code=e.response.get("Error", {}).get("Code"),
        )
        raise

    except Exception as e:
        logger.exception(
            "s3_upload_unexpected_error",
            local_path=str(local_path),
            error=str(e),
        )
        raise