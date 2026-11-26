"""Verified, no-clobber local SQLite snapshots for synthetic schemas v3/v4."""
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import tempfile
import time

from .connection import BUSY_TIMEOUT_MS, open_reader
from .schema_v3 import verify_forecast_schema

_SIDECARS = ("-wal", "-shm", "-journal")
_BACKUP_TIMEOUT_SECONDS = 30


def _sidecars(path: Path) -> tuple[Path, ...]:
    return tuple(Path(str(path) + suffix) for suffix in _SIDECARS)


def _require_unoccupied(path: Path) -> None:
    for candidate in (path, *_sidecars(path)):
        # lexists also rejects dangling symlinks.
        if os.path.lexists(candidate):
            raise FileExistsError(f"backup destination occupied: {candidate}")


def _verify(conn: sqlite3.Connection) -> None:
    verify_forecast_schema(conn)
    if conn.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
        raise ValueError("SQLite integrity check failed")


def _copy_verified(source: Path, destination: Path) -> Path:
    source = Path(source)
    destination = Path(destination)
    if not source.exists():
        raise FileNotFoundError(source)
    if not source.is_file():
        raise ValueError("backup source must be a regular file")
    if not destination.parent.is_dir():
        raise FileNotFoundError(destination.parent)
    _require_unoccupied(destination)

    # An exclusive name in the destination directory keeps publication local
    # to the same filesystem. No existing destination is ever opened.
    fd, name = tempfile.mkstemp(prefix=".atp-lab-backup-", suffix=".sqlite",
                                dir=destination.parent)
    staged = Path(name)
    try:
        os.close(fd)
        deadline = time.monotonic() + _BACKUP_TIMEOUT_SECONDS

        def progress(status: int, remaining: int, total: int) -> None:
            if status != sqlite3.SQLITE_DONE and time.monotonic() > deadline:
                raise TimeoutError("SQLite backup did not finish within its retry budget")

        with closing(open_reader(source)) as reader:
            # The SQLite backup API observes committed pages, including WAL.
            # No checkpoint or write is issued on the live database.
            with closing(sqlite3.connect(staged.resolve().as_uri() + "?mode=rw",
                                         uri=True, isolation_level=None)) as copy:
                copy.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
                reader.backup(copy, pages=128, progress=progress, sleep=0.05)
                if copy.execute("PRAGMA journal_mode = DELETE").fetchone()[0] != "delete":
                    raise ValueError("cannot create standalone SQLite snapshot")
                copy.execute("PRAGMA foreign_keys = ON")
                _verify(copy)

        # Verify the closed, independently openable file before publishing.
        if any(os.path.lexists(path) for path in _sidecars(staged)):
            raise ValueError("staged snapshot is not a standalone SQLite file")
        with closing(open_reader(staged)) as verification:
            _verify(verification)
        _require_unoccupied(destination)
        # Hard-link creation is atomic and fails if the target exists.
        # No rename/replace fallback on unsupported filesystems.
        os.link(staged, destination)
        return destination
    finally:
        for path in (*_sidecars(staged), staged):
            path.unlink(missing_ok=True)


def backup_database(source: Path, destination: Path) -> Path:
    """Create a verified standalone copy of a committed synthetic v3/v4 DB."""
    return _copy_verified(source, destination)


def restore_database(backup: Path, destination: Path) -> Path:
    """Verify and restore a snapshot to a new path; never replace a live DB."""
    return _copy_verified(backup, destination)
