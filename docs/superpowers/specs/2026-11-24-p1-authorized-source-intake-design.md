# P1.4d — Licensed Historical Correction Intake (2026-11-24)

## Context
Issue #17: February 2024 source has zero raw dated rows in pinned annual CSV despite twelve official events and twelve separate legacy tournament IDs. Historic HTML index is NOT licensed match-level results. No training, stake or honest positive ROI claims can be made.

## Scope
Build a **fail-closed, local-file intake report** binding one proposed correction artifact to original inventory SHA, byte size, content SHA, event scope, provider URL, explicit rights evidence and independent draw review evidence. File is never copied, parsed as model-ready data, or committed. This stage is distinct from actual match/draw reconciliation.

## Approaches
A) Scrape official / legacy pages and label outcomes → rejected: rights and draw completeness unknown.
B) Accept self-signed manifest as full model-training certification → rejected: would allow arbitrary unverified claims to unlock training.
C) **Selected:** check shape, local bytes and scope; distinguish trusted *source-rights evidence* from untrusted self-reported claims; report quarantined status. Even a source passing intake is **not** sufficient to train absent independent participant/draw completeness and chronological features.

## Contracts
- Version `P1_AUTHORIZED_SOURCE_INTAKE_1`; all fields allowlisted, no silent extras. `inventory_sha256` must match the supplied independently hashed inventory file.
- `source`: `name` (basename only), `sha256`, `size_bytes`, `source_url`, `retrieved_at_utc`, `format` (CSV only), `row_count_claimed`. SHA and bytes checked against local file; rows are NOT trusted or interpreted for outcomes.
- `permission`: `scope`, `evidence_url`, `report_id`, `report_sha256`, `ai_training_allowed` and `commercial_use_allowed`. Rights approved only if an independently provided trusted report registry maps `report_id` to exact hash; mere boolean or a linked HTML page cannot grant rights. A legacy index page must always be rejected as a correction result source.
- `draw_review`: `report_id`, `report_sha256`, `verified_official_match_ids`, `complete_main_draw` booleans; even if attested, untrusted claims do not confer draw certification. This module does NOT validate draws, and all readiness output stays fail-closed.
- `scope_event_keys`: explicit nonempty unique subset of official 2024 February event IDs; unmatched values rejected. No synthetic data joins.
- `status`: `NO_AUTHORIZED_HISTORICAL_REPAIR_SOURCE` when permission evidence absent/untrusted; `SOURCE_PERMISSION_REVIEWED_MATCH_AUDIT_PENDING` when rights receipt trusted and bytes match; still `eligible_for_model_training=0` and `allocation_enabled=false` and `stake=0`. A permission report is a review artifact, not a cryptographic proof of the legal grant.

## Output/CLI
`python -m atp_gate historical-source-intake <artifact.csv> <manifest.json> <inventory.json> <official.json> [--out reports/...]`
Output report lives only where explicitly requested (normally ignored `reports/`). No input overwrite, no filesystem changes to artifact. Source bytes hash computed streaming. Reports use `HISTORICAL_RESEARCH_ONLY`, no T−60 provenance.

## Tests
Missing artifact, tampered bytes, duplicate event IDs, wrong inventory SHA, malformed report SHA, licensing self-attestation only, legacy HTML URL, incorrect artifact basename, false/empty permission, future timestamp, input overwrite. For constructed synthetic source and trusted rights map, status advances only to **match audit pending**, never model-training eligibility.
