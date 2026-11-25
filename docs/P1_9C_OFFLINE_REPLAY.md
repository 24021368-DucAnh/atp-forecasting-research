# Exact pinned cohort replay (P1.9c)

From repository root, with the project's Python environment installed:

Windows PowerShell:
```powershell
.\.venv\Scripts\python.exe -m scripts.p1_8c_cohort_research --local-dir ".\data\tml_pinned"
```
Linux:
```bash
python -m scripts.p1_8c_cohort_research --local-dir ./data/tml_pinned
```
Use authorized local **raw** CSV bytes matching the original_sha256 pins in src/atp_gate/tml_cohort_manifest.py, one file per 2021–2025 season. Names must be YYYY.csv or YYYY-<expected SHA256>.csv; do not supply both. Do not supply derived files. Never distribute the original provider CSVs. Wrong/missing/ambiguous inputs return error/exit 2. The offline mode does not fetch anything, and the old archived 2025 comparison is marked NOT_RUN. Default no-argument command still explicitly acquires source bytes from the fixed Git blob API and publisher endpoint and fails closed on source drift. It is not a live service.
For generic research CLI, opt-in flag --normalize-level-a-2024 is available; it does not bypass the exact 2024 source pin. Reports distinguish nominal URL from observed acquisition mode; generic local inputs have null actual_fetch_uri. The pinned replay includes source and derived hashes separately.
