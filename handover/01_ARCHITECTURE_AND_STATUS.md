# Kiến trúc và trạng thái dự án

## Mục tiêu, ranh giới
ATP men's singles, nghiên cứu xác suất kết quả conditional on a retrospectively known matchup. Hướng đích: historical skill forecasting, đánh giá probability đúng thời gian, có khả năng tái lập. Không xem đây là hệ thống dự báo từng trận theo thời gian thực; dữ liệu không xác nhận actual match start/participant availability; no certified live decisions or odds.

## Kiến trúc và đường đi dữ liệu
```text
Provider sources (separate permissions, immutable raw SHA256)
  -> source_intake / source_profile / tournament registry / official-calendar audit
  -> TML source snapshot + identity audit + level-A normalization + duplicate audit
  -> locked research manifest + hash/row/fold preflight
  -> historical event timeline (tourney_date = event start; lag 28 days)
  -> fixed Elo baseline (global and shrinkage surface)
  -> matched-cohort scoring, Brier, log loss, event-cluster bootstrap
  -> aggregate JSON evidence
  -> [next] pre-event feature table, chronological fit/calibration/development evaluation
Separate engineering boundary: input contract -> policy gate (fail closed) -> synthetic paper ledger/audit.
```
Existing generic feature/train/replay and scoring modules are present. Their existence is not evidence that ML has been validated on the new locked TML cohort. Do not conflate old 2026 partial-year study and new 2021–25 source. No current-match stats/labels may enter pre-event features.

| Layer | Code/document originals |
|---|---|
| Input/gate | contracts.py, feature_schema.py, policy.py; docs/INPUT_AUDIT.md |
| Source intake | source_intake.py, source_profile.py, tier_registry.py, valuebetennis_source.py, official_calendar_coverage.py |
| TML versioning and source review | tml_snapshot.py, tml_historical_audit.py, tml_identity_audit.py, tml_sackmann_crosscheck.py |
| Duplicate/manifest | tml_duplicate_sensitivity.py, tml_cohort_manifest.py |
| Fixed reference | tml_elo_experiment.py, scripts/p1_8c_cohort_research.py |
| Existing generic research | research_data.py, research_features.py, research_train.py, research_replay.py, fold_scoring.py |
| Separate risk integrity modules | period_risk.py, paper_ledger.py, paper_cash_history.py, paper_evidence_archive.py, quote_receipt.py, report_integrity.py |

## Evolution and status (not percentages)
| Track | Evidence delivered | Remaining |
|---|---|---|
| P0 engineering | Contracts, synthetic gate, risk/ledger/replay tests and paper evidence archive; PRs #20/#22/#32–34 | Independent review, integration acceptance; historical research only |
| P1 source audit | Source rights review, inventory/tier/crosswalk, event/round diagnostics, snapshots | Official full main-draw completeness and result/timing not verified |
| P1.7c | 2024 two exact-source ATP250 events normalized, 54 raw, 53 eligible | Whole draw certification pending |
| P1.8a | Stable ID/duplicate/chronology diagnostics on both source versions | Source inconsistencies not automatically repaired |
| P1.8b | Three sensitivity cohorts, exact clone collapse, all conflicting rows quarantine alternative | No official match ID inferred |
| P1.8c | Official profile identity corroboration, exact raw/derived SHA preflight, locked cohort | Reviewer, full official draw, source availability, rights for broader use |
| P2 fixed Elo | Actual source replay; 3 previously inspected chronological evaluation years | Separate calibration, P2.2 feature engineering and real-source ML, uncertainty and prospective evaluation |
| P2.3–2.5 | Generic experimental infrastructure exists | Fit/calibration separation, ablation, walk-forward, independent validation on locked cohort not done |
| P3/P4 | Quote-receipt/paper integrity engineering exists | No independent T−60 data, no production qualification; outside current offline goal |

## Core evidence
- `docs/research/p1_7c_level_a_normalization_20261125.json`: before/after level-A sensitivity.
- `docs/research/p1_8a_identity_audit_v2_20261125.json` and duplicate forensics.
- `docs/research/p1_8b_duplicate_sensitivity_20261125.json`: Original A/B/C eligible 12176/12173/12171, evaluated 7247/7247/7245. Revised 12623/12620/12620 and all 7694. Exact clone collapse selected for data quality, not retrospective score.
- `docs/research/p1_8c_cohort_manifest_20261125.json`: final frozen reference and official profile links.
- Full spec/plan/evidence history remains in original docs. Exact Git PR inventory in `05_REPOSITORY_SNAPSHOT.json`.

## Issues and uncertainty
2025 archived source had 489 blank match_num and 1 malformed row; revised fixed these but is a mutable publisher endpoint. 2025 Dubai conflicting group absent in revised source, 3 exact-clone records removed from 2021/22. Provider stable match key not official ATP canonical match ID. Two display name variations with same provider ID corroborated; no name-based ID merging. Embargo 28 days is an estimate, not proof of publication or event completion time. 2023–25 already inspected; repeated testing may overfit. Dependency ranges in pyproject are not a fully pinned lockfile. All CI pass is necessary but insufficient; no independent official-draw certification, calibration validation, or production readiness. Private local data/report history not accessible in this package. Earlier source scripts and reports are preserved as historical evidence and can have different cohorts and assumptions.
