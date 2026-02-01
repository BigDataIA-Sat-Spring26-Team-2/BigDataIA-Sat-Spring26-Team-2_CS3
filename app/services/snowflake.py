from app.config import get_settings
import snowflake.connector

def get_connection():
    settings = get_settings()

    print("SNOWFLAKE SETTINGS:", settings.SNOWFLAKE_DATABASE, settings.SNOWFLAKE_SCHEMA, settings.SNOWFLAKE_ROLE)
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

def test_snowflake_connection() -> bool:
    """
    Test Snowflake connection by executing a simple query.
    Returns True if connection is healthy, False otherwise.
    """
    conn = None
    cursor = None
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Simple test query
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        
        # Verify we got expected result
        return result is not None and result[0] == 1
        
    except snowflake.connector.errors.ProgrammingError as e:
        print(f"Snowflake programming error: {e}")
        return False
    except snowflake.connector.errors.DatabaseError as e:
        print(f"Snowflake database error: {e}")
        return False
    except Exception as e:
        print(f"Unexpected Snowflake error: {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


async def check_snowflake() -> str:
    """
    Health check function for Snowflake.
    Returns 'healthy' if connection works, 'unhealthy' otherwise.
    """
    try:
        is_healthy = test_snowflake_connection()
        return "healthy" if is_healthy else "unhealthy"
    except Exception as e:
        print(f"Snowflake health check failed: {e}")
        return "unhealthy"
