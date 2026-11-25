"""P1.9d regression contracts: dependency boundary and tracked-file integrity."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_research_imports_and_help_without_pydantic():
    code = """
import sys
class BlockPydantic:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'pydantic' or fullname.startswith('pydantic.'):
            raise ImportError('Pydantic intentionally unavailable')
sys.meta_path.insert(0, BlockPydantic())
import atp_gate.tml_elo_experiment
import atp_gate.tml_cohort_manifest
import atp_gate.__main__
assert 'pydantic' not in sys.modules
sys.argv = ['atp_gate', '--help']
try:
    atp_gate.__main__.main()
except SystemExit as exc:
    assert exc.code == 0
"""
    p = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                       env={**os.environ, "PYTHONPATH":str(ROOT/"src")},
                       capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, p.stdout+p.stderr


def test_public_exports_keep_identity():
    from atp_gate import DecisionInput, DecisionOutput, evaluate, apply_profit_lock
    from atp_gate import contracts, policy
    assert DecisionInput is contracts.DecisionInput
    assert DecisionOutput is contracts.DecisionOutput
    assert evaluate is policy.evaluate
    assert apply_profit_lock is policy.apply_profit_lock


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args])


def make_repo(tmp_path):
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "core.autocrlf", "false")
    (tmp_path/"z.txt").write_bytes(b"hello\n")
    (tmp_path/"a.txt").write_bytes(b"world\n")
    (tmp_path/"MANIFEST_SHA256.txt").write_bytes(b"stale\n")
    git(tmp_path, "add", ".")
    return tmp_path


def test_manifest_exact_sorted_tracked_bytes_and_self_exclusion(tmp_path):
    from scripts.repository_manifest import build_manifest
    root = make_repo(tmp_path)
    (root/"ignored.csv").write_bytes(b"private")
    expected = "".join(f"{hashlib.sha256((root/p).read_bytes()).hexdigest()}  {p}\n"
                       for p in ("a.txt", "z.txt"))
    assert build_manifest(root) == expected


def test_manifest_verifier_detects_dirty_file_and_stale_coverage(tmp_path):
    from scripts.repository_manifest import build_manifest, verify_manifest
    root = make_repo(tmp_path)
    manifest = root/"MANIFEST_SHA256.txt"
    manifest.write_text(build_manifest(root), encoding="utf-8")
    verify_manifest(root)
    (root/"a.txt").write_bytes(b"changed")
    with pytest.raises(ValueError, match="dirty|changed|mismatch"):
        verify_manifest(root)
    git(root, "add", "a.txt")
    with pytest.raises(ValueError, match="manifest|mismatch"):
        verify_manifest(root)


@pytest.mark.parametrize("os_name,version", [("ubuntu-latest","3.11"),("ubuntu-latest","3.12"),
                                             ("windows-latest","3.11"),("windows-latest","3.12")])
def test_environment_lock_exists_with_exact_runtime_pins(os_name, version):
    lock = ROOT/"requirements"/f"{os_name}-py{version}.txt"
    assert lock.is_file()
    lines = [line for line in lock.read_text(encoding="utf-8").splitlines()
             if line and not line.startswith("#")]
    assert all("==" in line and not any(c in line for c in (">", "<", "*")) for line in lines)
    names = {line.split("==")[0].lower() for line in lines}
    assert {"pydantic","numpy","pandas","scikit-learn","xgboost","pytest","openpyxl"} <= names
