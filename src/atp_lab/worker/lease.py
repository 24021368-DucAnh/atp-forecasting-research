"""Cross-platform single-worker lock with kernel-managed crash recovery."""

from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import tempfile
from typing import Any

import portalocker

LOCK_NAME = "worker.lock"
STATE_NAME = "worker.state.json"


@dataclass(frozen=True)
class LeaseStatus:
    state: str
    worker_id: str | None = None
    started_at: str | None = None
    host: str | None = None


def _lock_path(data_dir: Path) -> Path:
    return Path(data_dir) / LOCK_NAME


def _metadata(worker_id: str) -> dict[str, str]:
    return {
        "worker_id": worker_id,
        "started_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "host": socket.gethostname(),
    }


def _read_metadata(data_dir: Path) -> dict:
    path = Path(data_dir) / STATE_NAME
    try:
        if not path.is_file() or path.is_symlink():
            return {}
        raw = path.read_bytes()[:4096]
        value = json.loads(raw.decode("utf-8")) if raw else {}
        return value if type(value) is dict else {}
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}


class WorkerLease(AbstractContextManager):
    """An exclusive OS file lock; the kernel releases it after a crash."""

    def __init__(self, data_dir: Path, worker_id: str):
        if type(worker_id) is not str or not worker_id.startswith("SYN-"):
            raise ValueError("worker identity must be synthetic")
        self.path = _lock_path(data_dir)
        self.worker_id = worker_id
        self._lock: portalocker.Lock | None = None

    def __enter__(self) -> "WorkerLease":
        if not self.path.parent.is_dir():
            raise FileNotFoundError(self.path.parent)
        if self.path.is_symlink():
            raise ValueError("worker lock path cannot be a symlink")
        lock = portalocker.Lock(
            str(self.path), mode="a+b", timeout=0,
            flags=portalocker.LOCK_EX | portalocker.LOCK_NB,
        )
        try:
            handle = lock.acquire()
        except portalocker.exceptions.LockException as exc:
            raise RuntimeError("another ATP worker holds the local lease") from exc
        self._lock = lock
        try:
            del handle
            payload = json.dumps(_metadata(self.worker_id), sort_keys=True).encode("utf-8")
            fd, temp_name = tempfile.mkstemp(prefix=".worker-state-", dir=self.path.parent)
            try:
                with os.fdopen(fd, "wb") as state_file:
                    state_file.write(payload)
                    state_file.flush()
                    os.fsync(state_file.fileno())
                os.replace(temp_name, self.path.parent / STATE_NAME)
            finally:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)
        except BaseException:
            self._lock.release()
            self._lock = None
            raise
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        if self._lock is not None:
            self._lock.release()
            self._lock = None
        return False


def worker_lease(data_dir: Path, *, worker_id: str) -> WorkerLease:
    return WorkerLease(Path(data_dir), worker_id)


def read_lease(data_dir: Path) -> LeaseStatus:
    """Read status without creating files or trusting stale PID metadata."""
    path = _lock_path(data_dir)
    if not path.exists():
        return LeaseStatus("IDLE")
    if not path.is_file() or path.is_symlink():
        return LeaseStatus("UNAVAILABLE")
    try:
        lock = portalocker.Lock(
            str(path), mode="rb", timeout=0,
            flags=portalocker.LOCK_EX | portalocker.LOCK_NB,
        )
        handle = lock.acquire()
    except portalocker.exceptions.LockException:
        record = _read_metadata(path.parent)
        return LeaseStatus("ACTIVE", record.get("worker_id"),
                           record.get("started_at"), record.get("host"))
    try:
        raw = handle.read(4096)
    finally:
        lock.release()
    record = _read_metadata(path.parent)
    return LeaseStatus("IDLE", record.get("worker_id"),
                       record.get("started_at"), record.get("host"))
