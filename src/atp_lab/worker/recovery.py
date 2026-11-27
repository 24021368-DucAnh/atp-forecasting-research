"""Verified, no-clobber backup bundles for the newest local schema."""

from contextlib import closing
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import zipfile

from atp_lab.database.backup import backup_database
from atp_lab.database.connection import open_reader
from atp_lab.database.schema_v3 import verify_forecast_schema
from atp_lab.database.schema_v5 import verify_training_schema
from atp_lab.training.artifact import MAX_BYTES, decode_artifact

DATABASE_MEMBER = "atp_lab.sqlite"
MANIFEST_MEMBER = "manifest.json"
MAX_BUNDLE_BYTES = 1024 * 1024 * 1024


def _registered_artifacts(database: Path) -> dict[str, bytes]:
    with closing(open_reader(database)) as conn:
        verify_forecast_schema(conn)
        if conn.execute("PRAGMA user_version").fetchone()[0] != 5:
            return {}
        verify_training_schema(conn)
        rows = conn.execute("SELECT model_id,payload FROM candidate_artifacts ORDER BY model_id").fetchall()
    found = {}
    for model_id, payload in rows:
        candidate = decode_artifact(payload)
        if candidate.receipt.model_id != model_id:
            raise ValueError("candidate artifact registry identity mismatch")
        found[candidate.receipt.artifact_name] = payload.encode("utf-8")
    return found


def _manifest(files: dict[str, bytes]) -> bytes:
    records = [{"path": name, "size": len(raw), "sha256": sha256(raw).hexdigest()}
               for name, raw in sorted(files.items())]
    return json.dumps({"format": "ATP_V4_LOCAL_BACKUP_1", "files": records},
                      sort_keys=True, separators=(",", ":")).encode("utf-8")


def create_backup_bundle(database: Path, artifact_dir: Path, destination: Path) -> Path:
    """Back up SQLite and every registered JSON artifact as one verified ZIP."""
    database, artifact_dir, destination = map(Path, (database, artifact_dir, destination))
    if not database.is_file() or database.is_symlink():
        raise ValueError("backup source database must be a regular file")
    if not destination.parent.is_dir():
        raise FileNotFoundError(destination.parent)
    if os.path.lexists(destination):
        raise FileExistsError(destination)
    registered = _registered_artifacts(database)
    local = {}
    if artifact_dir.exists():
        if not artifact_dir.is_dir() or artifact_dir.is_symlink():
            raise ValueError("model artifact directory must be a regular directory")
        for path in artifact_dir.iterdir():
            if path.suffix.lower() != ".json":
                continue
            if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_BYTES:
                raise ValueError("model artifacts must be bounded regular JSON files")
            local[path.name] = path.read_bytes()
    if local != registered:
        raise ValueError("local model artifacts differ from the verified registry")

    stage_dir = Path(tempfile.mkdtemp(prefix=".atp-backup-", dir=destination.parent))
    staged_db = stage_dir / DATABASE_MEMBER
    staged_zip = stage_dir / "backup.zip"
    try:
        backup_database(database, staged_db)
        files = {DATABASE_MEMBER: staged_db.read_bytes()}
        for name, raw in registered.items():
            files[f"model_artifacts/{name}"] = raw
        files[MANIFEST_MEMBER] = _manifest(files)
        if sum(map(len, files.values())) > MAX_BUNDLE_BYTES:
            raise ValueError("backup bundle exceeds the configured size limit")
        with zipfile.ZipFile(staged_zip, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for name, raw in files.items():
                bundle.writestr(name, raw)
        _verify_bundle(staged_zip)
        if os.path.lexists(destination):
            raise FileExistsError(destination)
        os.link(staged_zip, destination)
        return destination
    finally:
        shutil.rmtree(stage_dir, ignore_errors=True)


def _read_bundle(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path, "r") as bundle:
        infos = bundle.infolist()
        if not infos or sum(item.file_size for item in infos) > MAX_BUNDLE_BYTES:
            raise ValueError("backup bundle exceeds the configured size limit")
        files = {}
        for item in infos:
            pure = PurePosixPath(item.filename)
            mode = (item.external_attr >> 16) & 0o170000
            if (item.is_dir() or pure.is_absolute() or ".." in pure.parts
                    or "\\" in item.filename or mode == stat.S_IFLNK
                    or item.filename in files):
                raise ValueError("unsafe or duplicate backup member")
            if item.filename != MANIFEST_MEMBER and item.filename != DATABASE_MEMBER:
                if len(pure.parts) != 2 or pure.parts[0] != "model_artifacts" or pure.suffix != ".json":
                    raise ValueError("unexpected backup member")
            files[item.filename] = bundle.read(item)
    manifest_raw = files.pop(MANIFEST_MEMBER, None)
    if manifest_raw is None:
        raise ValueError("backup manifest missing")
    try:
        manifest = json.loads(manifest_raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise ValueError("invalid backup manifest") from None
    if type(manifest) is not dict or set(manifest) != {"format", "files"} or manifest["format"] != "ATP_V4_LOCAL_BACKUP_1":
        raise ValueError("unsupported backup manifest")
    records = manifest["files"]
    if type(records) is not list or len(records) != len(files):
        raise ValueError("backup manifest file inventory mismatch")
    expected = {}
    for row in records:
        if type(row) is not dict or set(row) != {"path", "size", "sha256"}:
            raise ValueError("invalid backup file record")
        name = row["path"]
        raw = files.get(name)
        if (type(name) is not str or raw is None or row["size"] != len(raw)
                or row["sha256"] != sha256(raw).hexdigest() or name in expected):
            raise ValueError("backup file digest mismatch")
        expected[name] = raw
    if set(expected) != set(files) or DATABASE_MEMBER not in files:
        raise ValueError("backup file inventory incomplete")
    return expected


def _verify_bundle(path: Path) -> dict[str, bytes]:
    files = _read_bundle(path)
    for name, raw in files.items():
        if name.startswith("model_artifacts/"):
            if len(raw) > MAX_BYTES:
                raise ValueError("model artifact exceeds size limit")
            candidate = decode_artifact(raw.decode("utf-8"))
            if name != f"model_artifacts/{candidate.receipt.artifact_name}":
                raise ValueError("model artifact filename mismatch")
    with tempfile.TemporaryDirectory(prefix=".atp-verify-", dir=path.parent) as temp:
        database = Path(temp) / DATABASE_MEMBER
        database.write_bytes(files[DATABASE_MEMBER])
        with closing(open_reader(database)) as conn:
            verify_forecast_schema(conn)
            if conn.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise ValueError("backup database integrity check failed")
        expected = _registered_artifacts(database)
    actual = {name.removeprefix("model_artifacts/"): raw for name, raw in files.items()
              if name.startswith("model_artifacts/")}
    if actual != expected:
        raise ValueError("backup artifacts do not match the database registry")
    return files


def restore_backup_bundle(bundle_path: Path, destination: Path) -> Path:
    """Restore into a new data directory; the active database is never replaced."""
    bundle_path, destination = Path(bundle_path), Path(destination)
    if not bundle_path.is_file() or bundle_path.is_symlink():
        raise ValueError("backup must be a regular file")
    if not destination.parent.is_dir():
        raise FileNotFoundError(destination.parent)
    if os.path.lexists(destination):
        raise FileExistsError(destination)
    files = _verify_bundle(bundle_path)
    stage = Path(tempfile.mkdtemp(prefix=".atp-restore-", dir=destination.parent))
    published: list[tuple[Path, int, int, bool]] = []
    try:
        (stage / DATABASE_MEMBER).write_bytes(files[DATABASE_MEMBER])
        artifacts = {name.removeprefix("model_artifacts/"): raw
                     for name, raw in files.items() if name.startswith("model_artifacts/")}
        if artifacts:
            directory = stage / "model_artifacts"
            directory.mkdir()
            for name, raw in artifacts.items():
                (directory / name).write_bytes(raw)
        # Reserve the destination atomically so a concurrent path creator is
        # never replaced; then publish only files into our own new directory.
        destination.mkdir()
        destination_info = destination.stat()
        published.append((destination, destination_info.st_dev, destination_info.st_ino, True))
        for item in stage.iterdir():
            target = destination / item.name
            if item.is_dir():
                target.mkdir()
                directory_info = target.stat()
                published.append((target, directory_info.st_dev, directory_info.st_ino, True))
                for child in item.iterdir():
                    child_target = target / child.name
                    source_info = child.stat()
                    published.append((child_target, source_info.st_dev, source_info.st_ino, False))
                    os.link(child, child_target)
            else:
                source_info = item.stat()
                published.append((target, source_info.st_dev, source_info.st_ino, False))
                os.link(item, target)
        shutil.rmtree(stage)
        return destination
    except BaseException:
        for path, device, inode, is_directory in reversed(published):
            try:
                current = path.lstat()
                if (current.st_dev, current.st_ino) != (device, inode):
                    continue
                if is_directory:
                    path.rmdir()
                else:
                    path.unlink()
            except OSError:
                pass
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)
        raise
