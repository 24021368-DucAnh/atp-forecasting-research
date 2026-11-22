import csv
import json
import random
import os
import subprocess
import sys
from datetime import date,timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def call(*args):
    env={**os.environ,'PYTHONPATH':str(ROOT/'src')}
    return subprocess.run([sys.executable,'-m','atp_gate',*map(str,args)],
                          cwd=ROOT,capture_output=True,text=True,env=env)

def example_csv(path):
    fields=['ATP','Tournament','Date','Series','Surface','Round','Best of','Winner','Loser',
            'WRank','LRank','Comment','B365W','B365L']
    rng=random.Random(20261123)
    with path.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=fields)
        writer.writeheader()
        for i in range(120):
            day=date(2025,1,1)+timedelta(days=i)
            for j in range(4):
                a=(7*i+3*j)%20
                b=(a+1+i%7)%20
                y=int(rng.random()<0.52)
                winner_idx=a if y else b
                loser_idx=b if y else a
                writer.writerow(dict(ATP='1',Tournament='Demo',Date=day.strftime('%d/%m/%Y'),
                        Series='ATP500' if i%2==0 else 'ATP250',Surface='Clay' if i%3==0 else 'Hard',
                        Round='1st Round',**{'Best of':'3'},Winner=f'P{a:02d}' if y else f'P{b:02d}',
                        Loser=f'P{b:02d}' if y else f'P{a:02d}',WRank=10+winner_idx,LRank=10+loser_idx,
                        Comment='Completed',B365W=1.9,B365L=1.95))
    return path


def test_research_audit_outputs_explicit_day_only_label(tmp_path):
    proc=call('research-audit',example_csv(tmp_path/'a.csv'))
    assert proc.returncode==0,proc.stdout+' '+proc.stderr
    data=json.loads(proc.stdout)
    assert data['total_rows']==480
    assert data['accepted']>0
    assert data['t60_live_eligible']==0 and data['time_precision']=='DAY_ONLY'


def test_cli_research_train_writes_research_only_metrics(tmp_path):
    target=tmp_path/'report.json'
    proc=call('research-train',example_csv(tmp_path/'a.csv'),'--out',target,
              '--minimum-total','90','--minimum-target','20')
    assert proc.returncode==0,proc.stdout+' '+proc.stderr
    data=json.loads(target.read_text(encoding='utf-8'))
    assert data['live_eligible'] is False
    assert data['allocation_enabled'] is False
    assert data['splits']['holdout_n']>=20
    assert data['stake']==0
    assert json.loads(proc.stdout)['mode']=='HISTORICAL_RESEARCH_ONLY'


def test_cli_research_train_insufficient_data_does_not_write_report(tmp_path):
    p=tmp_path/'small.csv'
    p.write_text('Date,Series,Tournament,Winner,Loser,Surface,Round,Best of,Comment,B365W,B365L\n',encoding='utf-8')
    target=tmp_path/'report.json'
    proc=call('research-train',p,'--out',target)
    assert proc.returncode !=0
    assert not target.exists()
    assert 'Insufficient' in proc.stdout or 'INSUFFICIENT' in proc.stdout
