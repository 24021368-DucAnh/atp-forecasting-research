# P1.3b — Review a Valuebetennis tournament inventory for research blockers

`valuebetennis-review` is a **read-only anomaly and reconciliation check of a P1.3a JSON inventory**, not a trading system, an official ATP event catalog or a model-training command. It does not require reloading five provider CSVs.

## Windows PowerShell (project root, after merging PR and pulling main)

```powershell
git pull --ff-only
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m atp_gate valuebetennis-review reports\valuebetennis_tournaments_2022_2026.json --out reports\valuebetennis_inventory_review_2022_2026.json
```

Omit `--out` to print just the compact summary without writing anything.

## Checks and semantics

1. **Integrity:** Every tournament `round_counts` sum must equal its candidate-match count. Each `(UTC match year, provider tournament ID)` must be unique. Totals must match original P1.3a accepted counts and year-by-year totals. A mismatch returns `ERROR` with exit code 2 and does not create a successful review.
2. **Cross-calendar-year IDs:** A provider ID repeated in two UTC years is flagged, not automatically combined into an official tournament edition. An official edition identifier/canonical season-year must be verified before joins.
3. **Special event names:** Exact `ATP Cup -`, `United Cup -`, `Laver Cup -`, `Next Gen ATP Finals -`, `Nitto ATP Finals -` and `Olympics -` prefixes are flagged for manual scope review. This is **not** an exhaustive official classification or automatic approval of other entries.
4. **Missing raw final-code 12:** For source `Grand Slam`/`Masters` entries excluding flagged special formats, absence of the code is an investigation signal, not a guarantee a match did not occur. Provider's raw `tour` 0–12 classification is recorded as-is.
5. **Observed event-start gaps:** Gaps greater than 45 days between observed tournament start dates in the same UTC year, with starts in January–October, are flagged. These are **not** claims there were no matches in those days.

The command returns `status: REVIEW_REQUIRED` on a well-formed report, **even if no anomalies**: ATP tiers, draw eligibility, actual first serve and T−60 odds remain unverified. A zero command exit means the review ran, NOT that the source is approved.

## Real-file observations that motivated the audit

User's 2022–2026 file: `valuebetennis_tournaments_2022_2026.json`, SHA-256 `eccb403bb6c0874e30f4e304c7be23678d2d1e6db095fd9174ee1753a225665b` (snapshot analyzed 23 Nov 2026). Contains **323** UTC-year groups and **19,065** provisional ATP matches, all internally reconciled. Raw source CSV origin/hash matching the provider still not independently authenticated.

- **Nine IDs span two UTC years**, e.g. `10841` (United Cup 2022/23) and `12415` (Brisbane 2023/24).
- At least **416 provisional candidate rows** in **23 UTC-year groups** have one of the six special-event prefixes; the provider calls Nitto ATP Finals `Masters` even though it is **not** an ATP Masters 1000 event.
- **Australian Open 2024** (provider ID `12440`) last record 2024-01-23, with no provider codes `10` or `12`. The official men's singles final took place Jan 28: https://ausopen.com/articles/news/sinner-winner-italian-takes-first-major-ao-2024
- **Indian Wells 2024** (provider ID `12589`) contains only 47 provisional rows and no early round codes; same event in 2023 has 131. Official results archive for 2024: https://www.atptour.com/en/scores/results-archive?year=2024
- **2024 Shanghai** `13649` has no final code `12`; **2026 Rome** includes only 49 candidate rows, with no later-round codes.
- **2024** has a gap of 61 days between first-observed event starts on Jan 8 (Australian Open) and Mar 9 (Indian Wells), with no February first-observed event starts.

Do not impute unseen results, declare a year complete because it has observations, or use these snapshots for confidence in model calibration/market edge.

Official level distinction: ATP 250, ATP 500 and Masters 1000 are different ATP Tour categories: https://www.atptour.com/en/news/atp-tour ; the ATP calendar lists United Cup and Laver Cup as separate team events: https://www.atptour.com/en/news/2026-atp-tour-calendar-announced .

## Next gates

**P1.3c** must build a reviewed authoritative tournament-edition registry: independent official event tier, event edition year, exact main-draw definition, documented source links and confidence, with unresolved rows excluded (ATP250 history only, ATP500/Masters1000/Slams target). Separately reconcile systematic event/round data gaps. The historical research adapter stays **blocked** until these checks; odds opening/closing prices are **not** authenticated T−60 quotes.

Safeguards in every review: `tier_mapping_verified=false`, `main_draw_verified=false`, `t60_quote_verified=false`, `eligible_for_model_training=0`, `allocation_enabled=false`, `stake=0`.
