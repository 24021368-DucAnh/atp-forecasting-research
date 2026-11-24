# P1.8a — pinned source identity, completeness and chronology diagnostics

Issue #29; base d4f7f63; isolated stacked research branch. P1.7c CI 45446839517 passed 4/4.
Goal: quantify internal defects on exact historical snapshots before designing features, without claiming official match identity or actual match timestamps.

Contract: audit_tml_identity(paths, *, expected_sha256) returns aggregate-only source receipts and diagnostic counts. Require an exact season-to-SHA256 manifest, unique seasons, valid filenames and 50-column schema; malformed rows are counted, not reconstructed. Detect missing/nonnumeric/canonical-number aliases, duplicate source and unordered player-pair/round identities, contradictory winners, player-ID/display-name token collisions, invalid dates, previous-year starts and edition-level date/surface metadata variants. Display names are review leads only, not player-ID aliases. No name-based automatic joins.

Knockout graph checks use 250/500/M/G main-draw rounds R128,R64,R32,R16,QF,SF,F (plus exact pinned 2024 Doha and Los Cabos from P1.7c), never infer an official draw from nominal draw size. Count missing or multiple finals, eliminated player reappearance in later rounds, and graph connectivity. An internal graph may be complete while an omitted early-round match remains invisible; no verified completeness claim. Treat incomplete/retired results as source rows for structural audit, not as completed outcomes. Events with unsupported round formats are reported separately, not scored as knockouts.

Data contract: no source rows/player names/player identifiers in reports; no source edits, no training eligibility, no allocation. Aggregate counts and source receipts only. Reproduce original and revised 2025 source sets separately (exact prior SHA), retain all findings including adverse ones. Source rights personal noncommercial. Official draw reconciliation, player identity adjudication, precise result availability, and independent model validation remain separate gates.

Acceptance: RED tests then GREEN, full 4-job CI, real-source aggregate Python evidence, issue/PR ledger; no main merge. This phase is internal review, not certification. Ruling: use a separate diagnostic module, rather than altering Elo loader or auto-quarantining candidates, so previously locked results remain reproducible.
