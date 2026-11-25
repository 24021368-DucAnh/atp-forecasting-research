# P2B.1 Pinned Python Reproduction Plan

**Goal:** reproduce the existing retrospective skill study on exact historical bytes.
**Architecture:** isolated test harness fetching fixed Git blob objects; existing CLI unchanged; aggregate-only output.
**Tech stack:** Python 3.11 stdlib, existing atp_gate package, one-off GitHub Actions.
**Spec:** docs/superpowers/specs/2026-11-24-p2-pinned-python-reproduction.md

- [x] Pin five recorded source blob hashes and implement a bounded verification harness.
- [x] Run the existing CLI unchanged with fixed defaults on the verified bytes.
- [x] Compare the observed sample counts and metrics, report discrepancies without adjusting parameters.
- [x] Verify the actual job log, record evidence in issue #29 and preserve the no-market/no-allocation boundary.


## Execution record — 2026-11-24
- Actual Python run: [45352171915](https://github.com/24021368-DucAnh/atp-forecasting-research/actions/runs/45352171915), commit 50645e3. Five verified Git blob objects, 12,123 accepted rows, 7,194 test matchups; exact sample count reproduction and all rounded metric comparisons within 1e-6.
- Evidence: docs/research/p2_pinned_elo_reproduction_20261124.json and docs/research/p2_tml_selection_quality_20261124.json.
- Ruling: nominal website URLs in the CLI are not actual retrieval provenance for Git blob inputs. The evidence envelope preserves actual GitHub blob URLs and hashes.
- Ruling: 489 missing match numbers in nine August/September 2025 event groups are not random missingness. Require a corrected source revision or authoritative crosswalk; never synthesize IDs. Original evidence remains unchanged.
- Ruling: 2023–2025 are now inspected research history, not untouched final holdouts for subsequent model choice. Preregister future evaluation separately.
- Review: self-review of aggregate evidence and provenance, not independent approval. No model or market certification.
