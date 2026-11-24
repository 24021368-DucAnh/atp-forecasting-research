# P2B.1 — Reproduce the fixed historical Elo study in Python

Goal: run the existing Python CLI on the exact five historical TML GitHub blobs previously used by the independent preliminary calculation. No algorithm changes, fitting, tuning, financial metrics or live decisions. User's private noncommercial historical research only.

1. Fetch only the five public TML Git blob objects by the recorded SHA-1, via the GitHub public HTTPS API; decode base64, verify the actual Git blob object hash (header plus original bytes), and write local SHA256-qualified filenames under ignored data/. Reject malformed, oversize or mismatched content. Never print or upload raw rows. No credentials, no scraping or repeated scheduling.
2. Run the existing tml-elo-experiment CLI with defaults (2023–2025, fixed 28-day embargo, K=24, fixed surface weighting, bootstrap seed) on those exact inputs. Save only aggregate JSON; compare counts and scores against preliminary JS calculations, with explicit tolerance. Discrepancies are findings, not a reason to tune or alter the source.
3. Use a branch-scoped, one-off GitHub Actions reproduction job on the private repo; no change to main, no automatic production use. Record actual source SHA256 and counts, Python version, commit and aggregate metrics, no provider raw files or match-level results in artifacts.
4. If provider fetch fails, report the real failure and keep study unverified. This is not official ATP draw verification, an exact pre-match prediction, or evidence of market edge.

Acceptance: the CLI really executes, reports five pinned source hashes and three folds, retains all research-only flags and reports replication differences. No new production code. A separate review and local host replication remain possible.
