from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs/research/p2_4_fixed_ablation_evidence_20261125.json"


def reader():
    from atp_lab.historical import read_historical_evidence
    return read_historical_evidence


def test_historical_support_and_scope():
    view = reader()(EVIDENCE)
    assert view["scope"] == "HISTORICAL_DEVELOPMENT_ONLY"
    assert view["n"] == 7694
    assert len(view["models"]) == 18
    assert view["folds"] == [{"year": 2023, "n": 2600},
                             {"year": 2024, "n": 2647},
                             {"year": 2025, "n": 2447}]
    assert view["real_data_active"] is False
    assert view["model_validation_trusted"] is False


def test_fixed_historical_model_metrics():
    view = reader()(EVIDENCE)
    model = view["models"]["logistic_platt"]
    assert model["n"] == 7694
    assert model["correct"] == 4970
    assert model["accuracy"] == pytest.approx(4970 / 7694)
    assert model["log_loss"] == pytest.approx(0.6213113230318553, abs=1e-7)
    assert model["brier"] == pytest.approx(0.21651241497585688, abs=1e-7)
    assert model["coverage"] == 1.0
    assert all(m["n"] == 7694 for m in view["models"].values())


def test_tampered_evidence_rejected(tmp_path):
    path = tmp_path / "evidence.json"
    path.write_bytes(EVIDENCE.read_bytes() + b" ")
    with pytest.raises(ValueError):
        reader()(path)


def test_missing_evidence_rejected(tmp_path):
    with pytest.raises(ValueError):
        reader()(tmp_path / "missing.json")


def test_reader_does_not_modify_evidence(tmp_path):
    path = tmp_path / "copy.json"
    original = EVIDENCE.read_bytes()
    path.write_bytes(original)
    reader()(path)
    assert path.read_bytes() == original
