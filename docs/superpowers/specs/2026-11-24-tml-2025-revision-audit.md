# P1/P2 — TML 2025 source revision reconnaissance

Goal: determine whether the publisher's current 2025 CSV actually repairs the 489 blank match numbers in the pinned historical Git blob. This is personal noncommercial source research; no change to production policy, training acceptance, odds or allocation.

Selected approach: one explicit HTTPS fetch through the existing versioned TML updater; compare against the exact verified Git blob 1aff9b077cf4de7806b665ec0c6d8b4032a040f3. Preserve distinct provenance and original SHA256. No guessed IDs, fuzzy names or merged source records.

Use exact candidate identity (provider tournament ID, round, unordered provider-local player IDs) across ALL well-formed rows from both snapshots, not merely missing-ID rows. Ambiguous candidate groups are quarantined. A missing old match number is counted as a provider repair candidate only if a unique corresponding new row has a nonblank match number and unchanged winner/loser, start date, level, surface and score. Changes in other columns are reported separately. This is not independent official draw verification. Count missing, ambiguous, changed-result, unchanged missing, and repaired categories; reconcile old missing total. Compare existing numbered rows and additions/removals. Never print player records.

A bounded one-off workflow runs the analysis and reports aggregate JSON only. A real provider failure or unchanged snapshot is a valid finding, not a reason to synthesize identifiers. No raw file upload. Do not treat corrected full-cohort scores as matched comparisons; subsequent model comparison requires verified data and pre-registered cohort definitions.
