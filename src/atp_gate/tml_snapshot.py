"""Versioned, owner-invoked official TML CSV refresh, personal research only.

No raw data redistribution, overwrite, model promotion, odds scraping, or
background network activity. An explicit CLI run performs one HTTPS fetch.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import tempfile
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from .tml_historical_audit import TML_COLUMNS

ROOT_URL = "https://stats.tennismylife.org/data"
MAX_BYTES = 20 * 1024 * 1024
MIN_REFRESH = timedelta(hours=24)
_SHA = re.compile(r"^[a-f0-9]{64}$")
_HEADER_DIGEST = hashlib.sha256(",".join(TML_COLUMNS).encode("utf-8")).hexdigest()


def _fetch_official(url: str) -> bytes:
    """One bounded HTTPS download; do not follow redirects to another host."""
    req = Request(url, headers={"User-Agent": "ATP-Selective-Research/0.2 (private noncommercial)"})
    try:
        with urlopen(req, timeout=20) as response:
            final = urlsplit(response.geturl())
            if final.scheme != "https" or final.hostname != "stats.tennismylife.org":
                raise ValueError("official TML CSV redirected outside its HTTPS origin")
            content = response.read(MAX_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise ValueError("TML public download unavailable") from exc
    return content


def _check_csv(content: bytes, year: int) -> int:
    if not isinstance(content, bytes) or not 0 < len(content) <= MAX_BYTES:
        raise ValueError("TML CSV bytes empty, oversized or not a byte payload")
    try:
        text = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        if reader.fieldnames != TML_COLUMNS:
            raise ValueError("TML source CSV schema drift or invalid header")
        rows = 0
        keys: set[tuple[str, str]] = set()
        for record in reader:
            if None in record or any(v is None for v in record.values()):
                raise ValueError("TML CSV row with malformed column count")
            sid, match = record["tourney_id"], record["match_num"]
            if not sid or not match:
                raise ValueError("TML CSV row lacks match/tournament ID")
            key = (sid, match)
            if key in keys:
                raise ValueError("duplicate TML tournament/match identifier")
            keys.add(key)
            raw_date = record["tourney_date"]
            if len(raw_date) != 8 or not raw_date.isdigit():
                raise ValueError("TML CSV record has invalid season date")
            try:
                tournament_start = datetime.strptime(raw_date, "%Y%m%d").date()
            except ValueError as exc:
                raise ValueError("TML CSV record has invalid season date") from exc
            # ATP next-season tournaments can legitimately start in late
            # December of the previous calendar year (e.g. 2025 CSV:
            # 2024-12-29). Do not quarantine a valid season for that.
            if not (tournament_start.year == year or
                    (tournament_start.year == year - 1
                     and tournament_start.month == 12
                     and tournament_start.day >= 25)):
                raise ValueError("TML CSV record has unexpected season start date")
            if (not record["winner_id"] or not record["loser_id"]
                    or record["winner_id"] == record["loser_id"]):
                raise ValueError("TML CSV incomplete/invalid player IDs")
            rows += 1
    except (UnicodeError, csv.Error) as exc:
        raise ValueError("invalid TML CSV encoding/structure") from exc
    if rows == 0:
        raise ValueError("TML CSV contains no completed matches")
    return rows


def _atomic_write(path: Path, payload: bytes) -> None:
    """Write atomically into a private, owner-specified local directory."""
    fd, tempname = tempfile.mkstemp(prefix=".tml-tmp-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tempname, path)
    finally:
        if os.path.exists(tempname):
            os.unlink(tempname)


def _read_prior(folder: Path, year: int, at: datetime) -> dict | None:
    index_file = folder / "index.json"
    if not index_file.exists():
        return None
    try:
        prior = json.loads(index_file.read_text(encoding="utf-8"))
        sha = prior["latest_sha256"]
        if (not isinstance(sha, str) or not _SHA.fullmatch(sha)
                or prior["year"] != year or
                prior["source_url"] != f"{ROOT_URL}/{year}.csv"
                or prior["schema_sha256"] != _HEADER_DIGEST):
            raise ValueError("untrusted TML local index")
        last = datetime.fromisoformat(prior["last_checked_at_utc"])
        if last.tzinfo is None or last.utcoffset() is None or last > at:
            raise ValueError("invalid TML index timestamp")
        latest = folder / f"{year}-{sha}.csv"
        if not latest.is_file() or hashlib.sha256(latest.read_bytes()).hexdigest() != sha:
            raise ValueError("TML local snapshot missing or content hash corrupted")
        return prior
    except (OSError, UnicodeError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("untrusted or corrupted TML index/snapshot") from exc


def update_tml_season(
    year: int,
    root: Path,
    *,
    at: datetime,
    fetcher: Callable[[str], bytes] | None = None,
    force: bool = False,
) -> dict:
    """Download and version only the publisher's fixed seasonal CSV URL.

    Dry-run test mocks pass a fetcher; production uses bounded stdlib HTTPS.
    A successful snapshot remains untrusted for model training or betting.
    """
    if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("TML update check requires timezone-aware clock")
    at = at.astimezone(timezone.utc)
    if type(year) is not int or not 1968 <= year <= at.year:
        raise ValueError("unsupported or future TML season year")
    if type(force) is not bool:
        raise ValueError("force flag must be boolean")
    root = Path(root)
    url = f"{ROOT_URL}/{year}.csv"
    folder = root / str(year)
    prior = _read_prior(folder, year, at)
    if prior:
        last = datetime.fromisoformat(prior["last_checked_at_utc"])
        if not force and at - last < MIN_REFRESH:
            return _result("SKIPPED_INTERVAL", year, url, prior, folder)

    data = (fetcher if fetcher is not None else _fetch_official)(url)
    row_count = _check_csv(data, year)
    sha = hashlib.sha256(data).hexdigest()
    folder.mkdir(parents=True, exist_ok=True)
    snapshot = folder / f"{year}-{sha}.csv"
    if snapshot.exists():
        if hashlib.sha256(snapshot.read_bytes()).hexdigest() != sha:
            raise ValueError("existing TML snapshot content hash corrupted")
    else:
        _atomic_write(snapshot, data)

    index = {
        "year": year, "source_url": url,
        "latest_sha256": sha,
        "last_checked_at_utc": at.isoformat(),
        "snapshot_filename": snapshot.name,
        "source_rows": row_count,
        "schema_sha256": _HEADER_DIGEST,
        "mode": "PERSONAL_NONCOMMERCIAL_RESEARCH",
    }
    _atomic_write(folder / "index.json", (json.dumps(index, sort_keys=True, indent=2) + "\n").encode("utf-8"))
    status = (
        "UNCHANGED" if prior and prior["latest_sha256"] == sha
        else "NEW_SNAPSHOT_REVIEW_REQUIRED"
    )
    return _result(status, year, url, index, folder)


def _result(status: str, year: int, url: str, index: dict, folder: Path) -> dict:
    return {
        "status": status,
        "mode": "PERSONAL_NONCOMMERCIAL_RESEARCH",
        "year": year,
        "source_url": url,
        "sha256": index["latest_sha256"],
        "source_rows": index["source_rows"],
        "checked_at_utc": index["last_checked_at_utc"],
        "local_snapshot": str(folder / f"{year}-{index['latest_sha256']}.csv"),
        "license_scope": "PERSONAL_EDUCATIONAL_NONCOMMERCIAL_ONLY",
        "source_event_completeness_verified": False,
        "individual_match_start_verified": False,
        "t60_quote_verified": False,
        "eligible_for_model_training": 0,
        "allocation_enabled": False,
        "stake": 0,
        "warnings": [
            "VERSIONED_LOCAL_SNAPSHOT_NOT_REVIEWED",
            "SOURCE_BYTES_NOT_CERTIFIED_AS_OFFICIAL_MATCH_DRAW",
            "NO_RAW_CSV_REDISTRIBUTION_OR_AUTO_TRAINING",
        ],
    }
