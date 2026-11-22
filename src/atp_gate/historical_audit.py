"""Quality audit for tennis-data-style results/odds CSV.

Historical rows have match outcomes (WINNER/LOSER) and often no quote timestamp.
This module NEVER emits live eligible selections or claims a T-60 backtest.
"""
from __future__ import annotations

import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

TIERS = {"Grand Slam", "Masters 1000", "ATP500"}


def _odds_ok(row: dict[str,str]) -> bool:
    try:
        x,y = Decimal(row.get('B365W','')),Decimal(row.get('B365L',''))
        overround = 1/x + 1/y
        return x > 1 and y > 1 and Decimal('0.90') <= overround <= Decimal('1.35')
    except (InvalidOperation, ArithmeticError, TypeError):
        return False


def audit_tennis_data_csv(path: str | Path) -> dict:
    summary = dict(total_rows=0, tier_rows=0, duplicate_candidates=0, missing_odds=0,
                   walkover=0, retired=0, invalid_date=0, invalid_format=0,
                   completed_with_odds_unique=0, t60_live_eligible=0,
                   date_precision='DAY_ONLY', mode='HISTORICAL_RESEARCH_ONLY')
    seen: set[tuple[str, ...]] = set()
    with Path(path).open('r',encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        required={'Date','Series','Tournament','Winner','Loser','Round','Surface','Best of',
                  'Comment','B365W','B365L'}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f'missing historical CSV columns: {sorted(required-set(reader.fieldnames or []))}')
        for row in reader:
            summary['total_rows']+=1
            if row['Series'] not in TIERS:
                continue
            summary['tier_rows']+=1
            key=tuple((row.get(k) or '').strip().lower() for k in ('Date','Tournament','Winner','Loser','Round'))
            if key in seen:
                summary['duplicate_candidates']+=1
                continue
            seen.add(key)
            try:
                datetime.strptime(row['Date'].strip(),'%d/%m/%Y')
            except (TypeError, ValueError):
                summary['invalid_date']+=1
                continue
            fmt=5 if row['Series']=='Grand Slam' else 3
            try:
                if int(row['Best of']) != fmt:
                    summary['invalid_format']+=1
                    continue
            except (TypeError,ValueError):
                summary['invalid_format']+=1
                continue
            if not _odds_ok(row):
                summary['missing_odds']+=1
                continue
            status=(row['Comment'] or '').strip().lower()
            if 'walkover' in status or status=='w/o':
                summary['walkover']+=1
            elif 'retir' in status or status=='ret':
                summary['retired']+=1
            elif status=='completed':
                summary['completed_with_odds_unique']+=1
            # cannot verify a pre-match snapshot using winning-side priced outcomes
    return summary
