import os
import psycopg2
from psycopg2.extras import RealDictCursor

def get_db_connection():
    """
    Returns a connection to the PostgreSQL database.
    Uses environment variables if set (for Render), otherwise defaults to local settings.
    """
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        database=os.environ.get("DB_NAME", "IMApp"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "HDS800516usa"),
        cursor_factory=RealDictCursor  # optional: returns results as dicts
    )

# Test block: only runs when you execute this file directly
if __name__ == "__main__":
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT NOW();")
        result = cur.fetchone()
        print("✅ Database connection successful! Server time:", result["now"])
        cur.close()
        conn.close()
    except Exception as e:
        print("❌ Failed to connect to database:", e)