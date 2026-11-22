"""Fail-closed verification of a research report's attached input files."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from atp_gate.report_integrity import verify_research_report

ROOT = Path(__file__).resolve().parents[1]


def make_example(tmp_path, payload=b'ATP,Date\n5,2026-01-10\n'):
    csv = tmp_path / 'season.csv'
    csv.write_bytes(payload)
    report = tmp_path / 'report.json'
    report.write_text(json.dumps({
        'mode': 'HISTORICAL_RESEARCH_ONLY',
        'live_eligible': False,
        'allocation_enabled': False,
        'validation_report_trusted': False,
        'stake': 0,
        'data_audit': {'source_files': [
            {'name': csv.name, 'sha256': hashlib.sha256(payload).hexdigest(),
             'size_bytes': len(payload)}]},
        'splits': {'train_end': '2026-01-20', 'calibrate_start': '2026-01-21',
                   'calibrate_end': '2026-01-24', 'holdout_start': '2026-01-25'},
    }), encoding='utf-8')
    return csv, report


def test_matching_report_and_original_input_passes(tmp_path):
    csv, report = make_example(tmp_path)
    result = verify_research_report(report, [csv])
    assert result['status'] == 'MATCH'
    assert result['source_files_verified'] == 1
    assert result['allocation_enabled'] is False
    assert result['validation_report_trusted'] is False


def test_modified_input_is_rejected(tmp_path):
    csv, report = make_example(tmp_path)
    csv.write_bytes(b'ATP,Date\n5,2026-01-11\n')
    result = verify_research_report(report, [csv])
    assert result['status'] == 'REJECT'
    assert 'SOURCE_HASH_MISMATCH' in result['reasons']


def test_missing_and_unexpected_inputs_are_rejected(tmp_path):
    csv, report = make_example(tmp_path)
    assert 'SOURCE_SET_MISMATCH' in verify_research_report(report, [])['reasons']
    second = tmp_path / 'extra.csv'
    second.write_text('anything', encoding='utf-8')
    assert 'SOURCE_SET_MISMATCH' in verify_research_report(report, [csv, second])['reasons']


def test_filename_collision_cannot_be_used_to_pick_wrong_source(tmp_path):
    csv, report = make_example(tmp_path)
    folder = tmp_path / 'other'
    folder.mkdir()
    same_name = folder / csv.name
    same_name.write_bytes(csv.read_bytes())
    result = verify_research_report(report, [csv, same_name])
    assert result['status'] == 'REJECT'
    assert 'DUPLICATE_SOURCE_NAME' in result['reasons']


def test_changed_training_partition_order_is_rejected(tmp_path):
    csv, report = make_example(tmp_path)
    info = json.loads(report.read_text())
    info['splits']['calibrate_start'] = '2026-01-19'
    report.write_text(json.dumps(info), encoding='utf-8')
    result = verify_research_report(report, [csv])
    assert result['status'] == 'REJECT'
    assert 'INVALID_TEMPORAL_SPLIT' in result['reasons']


def test_report_attempting_live_allocation_is_rejected(tmp_path):
    csv, report = make_example(tmp_path)
    info = json.loads(report.read_text())
    info['allocation_enabled'] = True
    report.write_text(json.dumps(info), encoding='utf-8')
    result = verify_research_report(report, [csv])
    assert result['status'] == 'REJECT'
    assert 'UNSAFE_REPORT' in result['reasons']


def test_invalid_json_fails_closed(tmp_path):
    csv, report = make_example(tmp_path)
    report.write_text('{broken', encoding='utf-8')
    result = verify_research_report(report, [csv])
    assert result['status'] == 'REJECT'
    assert 'INVALID_REPORT' in result['reasons']


def test_cli_verify_returns_error_on_mutated_data(tmp_path):
    csv, report = make_example(tmp_path)
    env = {**os.environ, 'PYTHONPATH': str(ROOT / 'src')}

    def call():
        return subprocess.run([sys.executable, '-m', 'atp_gate', 'research-verify', str(report), str(csv)],
                              cwd=ROOT, capture_output=True, text=True, env=env)

    good = call()
    assert good.returncode == 0, good.stdout + good.stderr
    assert json.loads(good.stdout)['status'] == 'MATCH'
    csv.write_text('changed', encoding='utf-8')
    bad = call()
    assert bad.returncode != 0
    assert json.loads(bad.stdout)['status'] == 'REJECT'
