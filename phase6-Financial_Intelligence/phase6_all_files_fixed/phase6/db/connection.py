"""
Phase 1 -- Database Connection Layer (shared, reused unchanged from Phase 3/5)
Pooled PostgreSQL connections, configured entirely via environment
variables (no hardcoded host/user/password anywhere).

Required env vars:
    DB_HOST      (default: localhost)
    DB_PORT      (default: 5432)
    DB_NAME      (default: real_estate_db)
    DB_USER      (required, no default -- must be set explicitly)
    DB_PASSWORD  (required, no default -- must be set explicitly)
"""
import os
import contextlib
from psycopg2 import pool as pg_pool
from psycopg2.extras import RealDictCursor

_POOL = None


def _get_config():
    missing = [v for v in ("DB_USER", "DB_PASSWORD") if not os.environ.get(v)]
    if missing:
        raise RuntimeError(
            f"Missing required DB env vars: {missing}. "
            f"Set DB_USER and DB_PASSWORD (see .env.example)."
        )
    return {
        "host": os.environ.get("DB_HOST", "localhost"),
        "port": int(os.environ.get("DB_PORT", 5432)),
        "dbname": os.environ.get("DB_NAME", "real_estate_db"),
        "user": os.environ["DB_USER"],
        "password": os.environ["DB_PASSWORD"],
    }


def get_pool(minconn: int = 1, maxconn: int = 10):
    """Lazily initializes a global connection pool (one per process)."""
    global _POOL
    if _POOL is None:
        cfg = _get_config()
        _POOL = pg_pool.ThreadedConnectionPool(minconn, maxconn, **cfg)
    return _POOL


@contextlib.contextmanager
def get_connection():
    """Context manager: borrows a connection from the pool, returns it after use."""
    pool = get_pool()
    conn = pool.getconn()
    try:
        yield conn
    finally:
        pool.putconn(conn)


@contextlib.contextmanager
def get_cursor(dict_cursor: bool = True):
    """Context manager: yields a cursor, commits on success, rolls back on error."""
    with get_connection() as conn:
        cursor_factory = RealDictCursor if dict_cursor else None
        cur = conn.cursor(cursor_factory=cursor_factory)
        try:
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()


def health_check() -> dict:
    """Returns DB connectivity status + basic info. Used by /health endpoint."""
    try:
        with get_cursor() as cur:
            cur.execute("SELECT 1 AS ok, current_database() AS db, version() AS version;")
            row = cur.fetchone()
            cur.execute("SELECT COUNT(*) AS n FROM core.properties;")
            count_row = cur.fetchone()
        return {
            "status": "healthy",
            "database": row["db"],
            "postgres_version": row["version"].split(",")[0],
            "properties_row_count": count_row["n"],
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


def close_pool():
    global _POOL
    if _POOL is not None:
        _POOL.closeall()
        _POOL = None


if __name__ == "__main__":
    print(health_check())
