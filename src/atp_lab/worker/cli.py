"""Explicit offline worker CLI; nothing starts during app import or render."""

import argparse
from contextlib import closing
import json
from pathlib import Path
import sys

from atp_lab.dashboard.view import DashboardUnavailable, load_dashboard_view
from atp_lab.database.connection import open_reader
from atp_lab.database.schema_v3 import verify_forecast_schema
from .database import database_path, default_data_dir, initialize_database
from .demo import seed_demo
from .lease import worker_lease
from .recovery import create_backup_bundle, restore_backup_bundle


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="atp-lab", description="Offline synthetic ATP research worker")
    parser.add_argument("--version", action="version", version="ATP Forecasting Lab V4 (S7 offline)")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "status"):
        item = commands.add_parser(name, help=f"{name.title()} the local offline workspace")
        item.add_argument("--data-dir", type=Path, default=default_data_dir())
    demo = commands.add_parser("demo", help="Explicit synthetic-only demonstration")
    demo_commands = demo.add_subparsers(dest="demo_command", required=True)
    seed = demo_commands.add_parser("seed", help="Create deterministic offline synthetic history")
    seed.add_argument("--data-dir", type=Path, default=default_data_dir())
    backup = commands.add_parser("backup", help="Verify and save database plus model artifacts")
    backup.add_argument("--data-dir", type=Path, default=default_data_dir())
    backup.add_argument("--destination", type=Path, required=True)
    restore = commands.add_parser("restore", help="Restore a verified bundle to a new directory")
    restore.add_argument("--data-dir", type=Path, default=default_data_dir())
    restore.add_argument("--backup", type=Path, required=True)
    restore.add_argument("--destination", type=Path, required=True)
    return parser


def _verify_database(path: Path) -> None:
    with closing(open_reader(path)) as conn:
        verify_forecast_schema(conn)


def _emit(payload: dict) -> None:
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def _run(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    if args.command == "init":
        data_dir.mkdir(parents=True, exist_ok=True)
        with worker_lease(data_dir, worker_id="SYN-worker-init"):
            path = initialize_database(data_dir)
        _emit({"status": "READY", "database": str(path), "network": "DISABLED",
               "real_data": "LOCKED", "scheduler": "DISABLED"})
        return 0
    if args.command == "status":
        view = load_dashboard_view(database_path(data_dir), mode="SYNTHETIC_DEMO")
        _emit({"database_state": view.database_state, "error_code": view.error_code,
               "worker_state": view.health["worker_state"], "real_data": "LOCKED",
               "scheduler": "DISABLED", "overview": view.overview,
               "last_job": view.health["last_job"]})
        return 0
    if args.command == "demo" and args.demo_command == "seed":
        data_dir.mkdir(parents=True, exist_ok=True)
        with worker_lease(data_dir, worker_id="SYN-worker-demo-seed"):
            path = database_path(data_dir)
            _verify_database(path)
            counts = seed_demo(path)
        _emit({"status": "SUCCEEDED", "mode": "SYNTHETIC_DEMO", **counts,
               "network": "DISABLED", "real_data": "LOCKED"})
        return 0
    if args.command == "backup":
        with worker_lease(data_dir, worker_id="SYN-worker-backup"):
            path = database_path(data_dir)
            _verify_database(path)
            destination = create_backup_bundle(path, data_dir / "model_artifacts", args.destination)
        _emit({"status": "SUCCEEDED", "backup": str(destination), "verified": True})
        return 0
    if args.command == "restore":
        with worker_lease(data_dir, worker_id="SYN-worker-restore"):
            restored = restore_backup_bundle(args.backup, args.destination)
        _emit({"status": "SUCCEEDED", "restored_data_dir": str(restored), "verified": True})
        return 0
    raise ValueError("unsupported worker command")


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        return _run(args)
    except (DashboardUnavailable, OSError, RuntimeError, ValueError, ImportError) as exc:
        print(f"atp-lab: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
