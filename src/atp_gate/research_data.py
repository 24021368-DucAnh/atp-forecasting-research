"""Research-only reader of historical ATP winner/loser + odds files.

Each record already contains its outcome, so NEVER treat this as a T−60
pre-match odds feed. Canonical A/B order is independent of the winner column.
"""
from __future__ import annotations

import csv
import hashlib
import re
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

TIERS = {
    'grand slam': 'GRAND_SLAM', 'masters 1000': 'MASTERS_1000',
    'masters': 'MASTERS_1000', 'atp500': 'ATP_500', 'atp 500': 'ATP_500',
    'atp250': 'ATP_250', 'atp 250': 'ATP_250',
}
SURFACES = {'hard': 'Hard', 'clay': 'Clay', 'grass': 'Grass'}
REQUIRED = {'Date', 'Series', 'Tournament', 'Winner', 'Loser',
            'Surface', 'Round', 'Best of', 'Comment', 'B365W', 'B365L'}


@dataclass(frozen=True)
class HistoricalMatch:
    day: date
    tournament: str
    tier: str
    round_name: str
    surface: str
    player_a: str
    player_b: str
    y: int
    rank_a: float | None
    rank_b: float | None
    odds_a: float | None
    odds_b: float | None
    source_row: str


def _day(raw: str) -> date:
    for fmt in ('%d/%m/%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            pass
    raise ValueError('unsupported date')


def _rank(raw: str | None) -> float | None:
    try:
        n = float(raw or '')
        return n if 0 < n <= 10000 else None
    except (ValueError, TypeError):
        return None


def _odds(w: str | None, l: str | None) -> tuple[float | None, float | None]:
    try:
        ow, ol = float(w or ''), float(l or '')
        overround = 1.0 / ow + 1.0 / ol
        if ow > 1.0 and ol > 1.0 and 0.90 <= overround <= 1.35:
            return ow, ol
    except (ValueError, ZeroDivisionError, OverflowError, TypeError):
        pass
    return None, None



@contextmanager
def _source_rows(path: Path):
    """Yield (column names, iterator[(line_number, str-only row)])."""
    if path.suffix.lower() == '.csv':
        with path.open('r', encoding='utf-8-sig', newline='') as handle:
            reader=csv.DictReader(handle)
            yield reader.fieldnames or [], enumerate(reader, 2)
    elif path.suffix.lower() == '.xlsx':
        try:
            from openpyxl import load_workbook
        except ImportError as exc:
            raise RuntimeError('XLSX requires openpyxl: pip install -e ".[ml,test]"') from exc
        wb=load_workbook(path, read_only=True, data_only=True)
        try:
            sheet=wb.active
            it=sheet.iter_rows(values_only=True)
            header=[str(k or '') for k in next(it, ())]
            def convert(value):
                if value is None:
                    return ''
                if isinstance(value, datetime):
                    return value.strftime('%d/%m/%Y')
                return str(value)
            yield header, ((i,dict(zip(header,(convert(v) for v in row))))
                           for i,row in enumerate(it,2))
        finally:
            wb.close()
    else:
        raise ValueError('unsupported historical input format: use .csv or .xlsx')


def load_historical_matches(paths: str | Path | Iterable[str | Path]) -> tuple[list[HistoricalMatch], dict]:
    """Load ATP winner/loser CSVs; do not infer match times or stable player IDs."""
    if isinstance(paths, (str, Path)):
        paths = [paths]
    sources = [Path(p) for p in paths]
    if not sources:
        raise ValueError('at least one research CSV is required')
    counters: dict[str, object] = dict(
        total_rows=0, accepted=0, duplicate=0, bad_date=0, bad_format=0,
        unsupported_tier=0, unsupported_surface=0, not_completed=0,
        missing_player=0, missing_or_invalid_odds=0, missing_rank=0,
        time_precision='DAY_ONLY', t60_live_eligible=0,
        source_identity_verified=False, mode='HISTORICAL_RESEARCH_ONLY', source_files=[])
    matches: list[HistoricalMatch] = []
    keys: set[tuple] = set()
    for path in sources:
        digest=hashlib.sha256()
        with path.open('rb') as raw:
            for chunk in iter(lambda:raw.read(1024*1024),b''):
                digest.update(chunk)
        counters['source_files'].append({'name':path.name,'sha256':digest.hexdigest(),
                                         'size_bytes':path.stat().st_size})
        with _source_rows(path) as (fieldnames, rows):
            missing = REQUIRED - set(fieldnames)
            if missing:
                raise ValueError(f'missing columns in {path.name}: {sorted(missing)}')
            for line_number, row in rows:
                counters['total_rows'] += 1
                # tennis-data.co.uk's 'ATP' column is a season-local *tournament
                # sequence number* (e.g. 5 for a Grand Slam, 16 for a Masters).
                # It is NOT a boolean ATP-tour flag. Tour eligibility comes from
                # source provenance; tournament tier comes from 'Series'.
                if 'ATP' in row and not re.fullmatch(
                        r'[1-9][0-9]*(?:\.0+)?', str(row['ATP'] or '').strip()):
                    counters['bad_format'] += 1
                    continue
                tier = TIERS.get((row['Series'] or '').strip().casefold())
                if tier is None:
                    counters['unsupported_tier'] += 1
                    continue
                surface = SURFACES.get((row['Surface'] or '').strip().casefold())
                if surface is None:
                    counters['unsupported_surface'] += 1
                    continue
                status = (row['Comment'] or '').strip().casefold()
                if status != 'completed':
                    counters['not_completed'] += 1
                    continue
                try:
                    day = _day(row['Date'])
                except (TypeError, ValueError):
                    counters['bad_date'] += 1
                    continue
                try:
                    best_of = int((row['Best of'] or '').strip())
                except ValueError:
                    best_of = -1
                if best_of != (5 if tier == 'GRAND_SLAM' else 3):
                    counters['bad_format'] += 1
                    continue
                winner = (row['Winner'] or '').strip()
                loser = (row['Loser'] or '').strip()
                if not winner or not loser or winner.casefold() == loser.casefold():
                    counters['missing_player'] += 1
                    continue
                names = sorted((winner, loser), key=lambda n: (n.casefold(), n))
                key = (day, (row['Tournament'] or '').strip().casefold(),
                       (row['Round'] or '').strip().casefold(),
                       names[0].casefold(), names[1].casefold())
                if key in keys:
                    counters['duplicate'] += 1
                    continue
                keys.add(key)
                odds_w, odds_l = _odds(row['B365W'], row['B365L'])
                if odds_w is None:
                    counters['missing_or_invalid_odds'] += 1
                rank_w, rank_l = _rank(row.get('WRank')), _rank(row.get('LRank'))
                if rank_w is None or rank_l is None:
                    counters['missing_rank'] += 1
                winner_first = names[0] == winner
                m = HistoricalMatch(
                    day=day, tournament=(row['Tournament'] or '').strip(), tier=tier,
                    round_name=(row['Round'] or '').strip(), surface=surface,
                    player_a=names[0], player_b=names[1], y=int(winner_first),
                    rank_a=rank_w if winner_first else rank_l,
                    rank_b=rank_l if winner_first else rank_w,
                    odds_a=odds_w if winner_first else odds_l,
                    odds_b=odds_l if winner_first else odds_w,
                    source_row=f'{path.name}:{line_number}',
                )
                matches.append(m)
                counters['accepted'] += 1
    matches.sort(key=lambda m: (m.day, m.tournament.casefold(), m.round_name.casefold(),
                                m.player_a.casefold(), m.player_b.casefold()))
    return matches, counters
