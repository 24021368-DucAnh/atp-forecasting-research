# Experiment report input integrity (P0)

This tool answers one narrow question: **does a saved research report refer to exactly these unchanged source file bytes, and do its high-level dates/safety flags remain well formed?**

It does **not** reproduce the model fit, validate the labels, confirm a market edge, prove the odds existed at T-60, or authorize live capital allocation.

## Usage (PowerShell 5.1, from project root)

Once this PR is merged and installed locally:

```powershell
git pull --ff-only
.\.venv\Scripts\python.exe -m atp_gate research-verify reports\ATP_2026_research.json data\ATP_2026.csv
```

Expected output for unchanged input and report:

```json
{
  "status": "MATCH",
  "mode": "HISTORICAL_RESEARCH_ONLY",
  "source_files_verified": 1,
  "reasons": [],
  "live_eligible": false,
  "allocation_enabled": false,
  "validation_report_trusted": false,
  "stake": 0,
  "scope": "INPUT_BYTES_AND_REPORT_SAFETY_ONLY"
}
```

A modified, missing or unexpected CSV is rejected; nonzero CLI exit status is returned. For multiple source files, pass every original file named in `data_audit.source_files`. Source basenames must be unambiguous.

## What gets checked

- Every file's original byte length and SHA-256 digest matches `data_audit.source_files`.
- The exact file basename set matches the report manifest; duplicate basenames are rejected.
- The chronological boundaries satisfy `train_end < calibrate_start <= calibrate_end < holdout_start`.
- The report remains research-only with `stake == 0`, no live allocation, and no trusted validation claim.
- Malformed JSON, manifest metadata, and unreadable files are rejected without claiming success.

## Limitations and source policy

- SHA-256 comparison only protects against unintended source changes relative to the supplied manifest. It does not make the report authentic: the report and hashes could both be modified. No signature, independent trusted evidence registry or model recomputation is performed.
- This does not detect label leakage, incorrect player ID matching, incomplete feature history or price-timestamp deficiencies.
- `data/` and `reports/` stay ignored by Git. Keep controlled source copies in an appropriate lawful store; never push private data, account keys or licensed datasets.
- The source CSV can be used for historical research only where permitted. Do not turn this check into approval of a betting strategy.
