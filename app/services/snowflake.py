from app.config import get_settings
import snowflake.connector

def get_connection():
    settings = get_settings()

    conn_kwargs = dict(
        account=settings.SNOWFLAKE_ACCOUNT,
        user=settings.SNOWFLAKE_USER,
        password=settings.SNOWFLAKE_PASSWORD,
        database=settings.SNOWFLAKE_DATABASE,
        schema=settings.SNOWFLAKE_SCHEMA,
        warehouse=settings.SNOWFLAKE_WAREHOUSE,
        role=settings.SNOWFLAKE_ROLE,
    )

    # Only set role if provided
    if getattr(settings, "SNOWFLAKE_ROLE", None):
        conn_kwargs["role"] = settings.SNOWFLAKE_ROLE

    return snowflake.connector.connect(**conn_kwargs)

def test_snowflake_connection():
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        return result
    finally:
        cursor.close()
        conn.close()


async def check_snowflake() -> str:
    return "healthy"
