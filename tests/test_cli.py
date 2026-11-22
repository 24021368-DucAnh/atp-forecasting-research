import json
import os
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def cli(*args):
    env={**os.environ,'PYTHONPATH':str(ROOT/'src')}
    p=subprocess.run([sys.executable,'-m','atp_gate',*args],cwd=ROOT,env=env,
                     text=True,capture_output=True,timeout=20)
    return p,json.loads(p.stdout)


def test_demo_is_untrusted_and_never_allocates_money():
    p,data=cli('evaluate','examples/synthetic_unvalidated.json')
    assert p.returncode==0
    assert data['decision']=='ABSTAIN' and float(data['stake'])==0
    assert 'UNTRUSTED_VALIDATION_REPORT' in data['reasons']


def test_invalid_fixture_returns_machine_readable_rejection(tmp_path):
    sample=tmp_path/'missing.json';sample.write_text('{}',encoding='utf-8')
    p,data=cli('evaluate',str(sample))
    assert p.returncode==2
    assert data['decision']=='ABSTAIN' and data['reasons']==['INVALID_CONTRACT']


def test_historical_audit_cli_marks_research_only():
    p,data=cli('audit','examples/historical_toy.csv')
    assert p.returncode==0
    assert data['mode']=='HISTORICAL_RESEARCH_ONLY'
    assert data['t60_live_eligible']==0


def test_missing_timezone_is_reported_as_environment_issue(monkeypatch, capsys):
    """A missing Windows IANA database must not be mislabeled invalid JSON."""
    from zoneinfo import ZoneInfoNotFoundError
    from atp_gate import __main__ as app_cli
    sample = ROOT / 'examples' / 'synthetic_unvalidated.json'

    def fail_timezone(_):
        raise ZoneInfoNotFoundError('No time zone found with key Asia/Bangkok')

    monkeypatch.setattr(app_cli, 'evaluate', fail_timezone)
    monkeypatch.setattr(sys, 'argv', ['atp_gate', 'evaluate', str(sample)])
    result = app_cli.main()
    printed = json.loads(capsys.readouterr().out)
    assert result == 3
    assert printed['decision'] == 'ABSTAIN'
    assert printed['reasons'] == ['TIMEZONE_DATABASE_MISSING']
