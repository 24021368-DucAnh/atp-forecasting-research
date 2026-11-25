# P1.6 / P2.1 — Fixed-baseline source revision sensitivity

**Goal:** establish actual revised event metadata and measure sensitivity of the unchanged historical skill baseline to a publisher revision.
**Architecture:** existing verified Git blob fetch, existing publisher updater, existing Elo CLI; no production model or policy changes.
**Constraints:** exact SHA256 for both sources; aggregate only; no source acceptance, no optimization, no market validation. The revised full-cohort metrics and old full-cohort metrics have different samples; do not label differences as paired model improvements. Event metadata evidence is not individual draw or start-time evidence.
**Primary references:** ATP 2025 calendar https://www.atptour.com/en/news/what-is-the-2025-atp-tour-calendar ; Shanghai schedule https://www.atptour.com/en/news/shanghai-2025-atp-masters-1000-history-draws-schedule .
**Steps:** run the two published snapshots through unchanged Python CLI on same fixed 2021–24 inputs, report event date/surface histograms, list level A event counts for registry review, compare metrics and counts as descriptive sensitivity; persist evidence from actual CI logs. Independent review remains pending.
