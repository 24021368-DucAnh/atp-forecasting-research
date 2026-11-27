"""Explicit local initialization and validated database access."""

from contextlib import closing
import os
from pathlib import Path

from atp_lab.database.connection import open_writer
from atp_lab.database.forecast import migrate_forecast
from atp_lab.database.identity import migrate_identity
from atp_lab.database.migrations import migrate
from atp_lab.database.schema_v3 import verify_forecast_schema
from atp_lab.database.schema_v4 import migrate_evaluation
from atp_lab.database.schema_v5 import migrate_training

DATABASE_NAME = "atp_lab.sqlite"


def default_data_dir() -> Path:
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA")
        return Path(root or Path.home() / "AppData" / "Local") / "ATP Forecasting Lab"
    root = os.environ.get("XDG_DATA_HOME")
    return Path(root) / "atp-forecasting-lab" if root else Path.home() / ".local/share/atp-forecasting-lab"


def database_path(data_dir: Path | None = None) -> Path:
    return (Path(data_dir) if data_dir is not None else default_data_dir()) / DATABASE_NAME


def initialize_database(data_dir: Path) -> Path:
    """Create a new v5 database or advance a recognized older V4 schema."""
    root = Path(data_dir)
    root.mkdir(parents=True, exist_ok=True)
    path = database_path(root)
    with closing(open_writer(path)) as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version == 0:
            migrate(conn)
            version = 1
        if version == 1:
            migrate_identity(conn)
            version = 2
        if version == 2:
            migrate_forecast(conn)
            version = 3
        if version == 3:
            migrate_evaluation(conn)
            version = 4
        if version == 4:
            migrate_training(conn)
        elif version != 5:
            raise ValueError("unsupported local database version")
        verify_forecast_schema(conn)
    return path
