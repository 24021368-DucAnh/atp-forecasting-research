import json
import zipfile
from atp_lab.dashboard.view import load_dashboard_view
from atp_lab.worker.cli import main


def test_init_status_backup_restore_are_explicit_and_no_clobber(tmp_path, capsys):
    data_dir = tmp_path / "local-data"
    assert main(["init", "--data-dir", str(data_dir)]) == 0
    database = data_dir / "atp_lab.sqlite"
    assert database.is_file()
    capsys.readouterr()

    assert main(["status", "--data-dir", str(data_dir)]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["database_state"] == "READY"
    assert status["worker_state"] == "IDLE"
    assert status["real_data"] == "LOCKED"

    saved = tmp_path / "backup.sqlite"
    assert main(["backup", "--data-dir", str(data_dir), "--destination", str(saved)]) == 0
    assert saved.is_file()
    assert main(["backup", "--data-dir", str(data_dir), "--destination", str(saved)]) != 0

    restored_root = tmp_path / "restored"
    assert main(["restore", "--data-dir", str(data_dir), "--backup", str(saved),
                 "--destination", str(restored_root)]) == 0
    assert (restored_root / "atp_lab.sqlite").is_file()
    assert main(["restore", "--data-dir", str(data_dir), "--backup", str(saved),
                 "--destination", str(restored_root)]) != 0


def test_seed_demo_populates_future_and_scored_history_without_external_data(tmp_path):
    data_dir = tmp_path / "local-data"
    assert main(["init", "--data-dir", str(data_dir)]) == 0
    assert main(["demo", "seed", "--data-dir", str(data_dir)]) == 0
    assert main(["demo", "seed", "--data-dir", str(data_dir)]) == 0

    view = load_dashboard_view(data_dir / "atp_lab.sqlite", mode="SYNTHETIC_DEMO")
    assert view.database_state == "READY"
    assert view.overview["fixtures"] >= 2
    assert view.overview["predictions"] >= 2
    assert view.overview["scored"] >= 1
    assert view.upcoming
    assert view.tournaments
    assert view.results
    assert view.models["active_model_id"] == "SYN-global-elo-v1"
    assert view.health["real_data"] == "LOCKED"


def test_restore_rejects_unexpected_bundle_members(tmp_path, capsys):
    data_dir = tmp_path / "local-data"
    assert main(["init", "--data-dir", str(data_dir)]) == 0
    capsys.readouterr()
    backup = tmp_path / "bundle.zip"
    assert main(["backup", "--data-dir", str(data_dir), "--destination", str(backup)]) == 0
    with zipfile.ZipFile(backup, "a") as bundle:
        bundle.writestr("../outside.txt", b"not allowed")
    destination = tmp_path / "restored"
    assert main(["restore", "--data-dir", str(data_dir), "--backup", str(backup),
                 "--destination", str(destination)]) == 2
    assert not destination.exists()
    assert not (tmp_path / "outside.txt").exists()
