# P1.4a — Official ATP Event Calendar Coverage Audit

## Why this exists

The user's first 2022–2026 Valuebetennis tournament inventory has a correctly reconciled 19,065 provisional source ATP candidates and 323 source tournament-year groups, but **its 2024 coverage has serious nonrandom omissions**. By directly inspecting the original uploaded JSON (SHA-256 `eccb403bb6c0874e30f4e304c7be23678d2d1e6db095fd9174ee1753a225665b`), none of the 56 groups in UTC year 2024 has first/last match observations in February. An ATP official 2024 calendar and results archive document **12 ATP Tour events actually held in February 2024** (eight ATP 250, four ATP 500). The calendar is not a training input and cannot repair these missing matches by itself.

Primary sources:
- [ATP 2024 historical results archive](https://www.atptour.com/en/scores/results-archive?year=2024): confirms 12 events held in February and their dates.
- [ATP official final 2024 calendar PDF](https://www.atptour.com/-/media/files/final-2024-atp-calendar.pdf): official 2024 tier classifications and scheduled dates; compare against archived results, as schedules change.
- [ATP Rotterdam 2024 event details](https://www.atptour.com/en/news/rotterdam-2024-history-draw-schedule): additional ATP 500 confirmation.

## Pinned reference and scope

`docs/registries/atp_2024_february_official_events_v1.json` is a **curated, partial official event schedule**, not a comprehensive calendar or a source of match-level official results. Contains Córdoba, Dallas, Marseille, Rotterdam, Buenos Aires, Delray Beach, Rio de Janeiro, Doha, Los Cabos, Acapulco, Dubai, and Santiago. Official classifications: 8 ATP 250 and 4 ATP 500. Do not infer ATP 250/500 from Valuebetennis's `categorie=Main tour`.

The reference includes exact original inventory SHA-256. A newly regenerated inventory cannot be classified using the stale reference: command exits `ERROR`. Rebuild only after comparing source digest, event names and date windows, never by manually suppressing the digest mismatch.

## Windows PowerShell after the PR is merged

In the existing ATP Selective Forecasting Lab project folder:

```powershell
git pull --ff-only
.\.venv\Scripts\python.exe -m pytest -q

.\.venv\Scripts\python.exe -m atp_gate valuebetennis-calendar-audit reports\valuebetennis_tournaments_2022_2026.json docs\registries\atp_2024_february_official_events_v1.json --out reports\valuebetennis_official_calendar_audit_2024_feb.json
```

The CLI prints compact JSON; optional full audit is saved to the **git-ignored** local `reports/` folder. Omitting `--out` makes it read-only.

For the exact input snapshot, the expected result is **12 official Feb events with `NO_SOURCE_EVENT_CANDIDATE`**, including **4 ATP 500** missing from the source inventory. This is a testable expectation based on our original user-uploaded JSON inspection, **not a claim that the new CLI has already run on their Windows machine**. `COVERAGE_REVIEW_REQUIRED` with exit code 0 means audit ran properly, **not** that the source passed quality acceptance.

## Match semantics / bias guardrails

The comparator looks for provisional source candidate rows with the same city suffix (right-hand part of `' - '`, case-folded and accent-normalized) in the **same UTC year**, within four days of the official event start/end date window. A single match produces `SOURCE_CANDIDATE_UNVERIFIED` — it does NOT certify actual event identity, main-draw eligibility, official edition year, doubles/qualifying exclusion or complete matches. Multiple matches are `AMBIGUOUS_SOURCE_CANDIDATES`. No matches are `NO_SOURCE_EVENT_CANDIDATE`; follow up with actual source logs to distinguish provider incompleteness from source filtering.

The official reference is limited to February 2024. It does not prove absence/presence in other months, let alone complete 2022–2026 coverage. The underlying dataset still has 9 cross-UTC-year event IDs, 23 special-format groups/416 provisional matches, known incomplete 2024 Australian Open and Indian Wells, and many unverified tournament tiers. Results archive and scheduled calendar must both be reviewed before event claims.

A report is never model-ready: `tier_mapping_verified=false`, `main_draw_verified=false`, `t60_quote_verified=false`, `eligible_for_model_training=0`, `allocation_enabled=false`, `stake=0`. Opening/closing odds are not authenticated T−60 market quotes, and missing results must not be imputed.

## Next research stages

- Extend the authoritative event reference to other 2024 months and independently reconcile actual results/official brackets with source IDs and player IDs, including retirements/walkovers and qualifiers.
- Investigate why the source omitted all February 2024 events (provider bulk export gaps, filtering, source revisions and source-row date/format anomalies). A missing event must never be treated as an ordinary negative match sample.
- Assemble a legally reusable, snapshot-pinned official match result source and a real main-draw filter. Before comparing models across seasons, require a **completeness matrix** by calendar event, match round, tier and year; exclude every unresolved mismatch.
- Only after scientific validity can P2 independent walk-forward evaluation proceed. Live/model stake permissions remain closed.
