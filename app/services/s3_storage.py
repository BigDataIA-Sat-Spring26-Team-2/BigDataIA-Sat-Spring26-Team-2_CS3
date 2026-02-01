# app/services/s3_storage.py
import boto3
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError
from app.config import get_settings

async def check_s3() -> str:
    """
    Health check for S3.
    Fails if credentials in .env are invalid.
    """
    try:
        settings = get_settings()
        print("S3 DEBUG CREDS:", settings.AWS_ACCESS_KEY_ID)
        # 1️⃣ Validate config exists
        if not all([
            settings.AWS_ACCESS_KEY_ID,
            settings.AWS_SECRET_ACCESS_KEY,
            settings.S3_BUCKET,
        ]):
            return "not_configured"

        # 2️⃣ Force boto3 to use ONLY these credentials
        session = boto3.session.Session(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )

        s3_client = session.client("s3")

        # 3️⃣ Make an auth-required call
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
