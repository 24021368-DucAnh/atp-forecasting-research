# P1.7c — opt-in pinned edition-tier normalization

Base: 8e00114. Issue #29 and its 7126610579 comment contain the independently replayed original-source sensitivity results. The existing 17-event inventory is documentation, not a blanket classification rule.

Ruling: code-owned, versioned registry subset rather than an arbitrary user-supplied JSON mapping. This prevents an unreviewed caller mapping from admitting special events. The report contains a SHA256 over canonical JSON of the registry with exact 2024 source pin and reviewed metadata. Both raw files and the default baseline remain unchanged. Unknown A stays excluded. This is an edition-level correction only; match-level draw identity remains unverified.

- RED: 8633513, CI run 45446218987, Ubuntu/Python 3.12: 8 failed (missing normalize_level_a_2024 argument), 379 passed.
- Implementation: 4d533e3; full CI must be verified independently before acceptance.
- Research command: python -m scripts.p1_7c_level_a_research. Fetches original five exact Git blobs and checks pinned byte SHA256; revised 2025 publisher bytes must match previously observed SHA256 or fail. Reports aggregate only, no raw CSV redistribution.
- Expected, not yet observed in Python: original 7194 -> 7247 evaluation rows, revised 7641 -> 7694; 54 reviewed raw rows, 53 eligible. Separate matched and expanded cohorts. No training certification, market edge, allocation, or release.
- CLI flag is not implemented in this change; the Python API is explicitly opt-in and the dedicated research script is the reproduction entrypoint.
