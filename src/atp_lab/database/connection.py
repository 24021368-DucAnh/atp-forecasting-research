"""Local SQLite connections; callers own connection lifetime."""
from pathlib import Path
import sqlite3

BUSY_TIMEOUT_MS = 5000


def _configure(conn: sqlite3.Connection) -> None:
    conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA foreign_keys = ON")
    if conn.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        raise RuntimeError("SQLite foreign key enforcement unavailable")


def open_writer(path: Path) -> sqlite3.Connection:
    """Open a local file-backed writer; transactions are explicit."""
    conn = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=rwc",
                           uri=True, isolation_level=None)
    try:
        _configure(conn)
        if conn.execute("PRAGMA journal_mode = WAL").fetchone()[0] != "wal":
            raise RuntimeError("SQLite WAL unavailable")
        return conn
    except BaseException:
        conn.close()
        raise


def open_reader(path: Path) -> sqlite3.Connection:
    """Open an existing database without write or create permission."""
    conn = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro",
                           uri=True, isolation_level=None)
    try:
        _configure(conn)
        conn.execute("PRAGMA query_only = ON")
        return conn
    except BaseException:
        conn.close()
        raise
