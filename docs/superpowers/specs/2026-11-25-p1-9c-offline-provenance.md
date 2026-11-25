# P1.9c — offline replay / acquisition provenance

Base 5a45054b (P1.9b final CI 45543339152 4/4, 428 tests); draft #42. Review findings P1-2, P1-3, CLI portion P2-3.

Contract:
- Existing default online invocation remains usable, with exact archive and revised 2025 pins. Local mode --local-dir reads a flat folder containing exactly one of YYYY.csv or YYYY-<expected SHA256>.csv per pinned season 2021–2025. Reject missing, ambiguous, oversize, symlink or hash mismatch. Never fallback to network; all bytes checked before profile/derivation/replay. Local folder untouched, derived snapshots temporary.
- Old 2025 archive profile is an optional comparison in online mode, not required for reproduction of the revised locked cohort; in local-only mode report it NOT_RUN and null rather than invent counts. Identity review counts for revised/derived still checked. No raw row or name-token output.
- Generic local Elo inventory distinguishes nominal publisher URL from actual acquisition URI (null when unobserved). Locked replay receipt reports local or verified Git blob or requested publisher endpoint, raw SHA and derived SHA separately. Do not claim publisher fetch for local files. Publisher requested endpoint is not proof of final redirect path or historical publication timestamp.
- CLI --normalize-level-a-2024 remains opt-in, same 2024 source pin and metadata guards.
- Preserve manifest digest and metrics from P1.8c, no data writes to repository. Full CI plus real-source replay with network acquisition followed by local-only replay with socket connections forbidden; compare cohort, hashes and aggregate, confirm different truthful acquisition modes. If publisher has drifted and exact source unavailable, report BLOCKED, do not substitute.
- Separate P1.9e handles full per-fold/CI and bootstrap. No training certification, official draw verification or allocation. No main merge. Fresh independent review required later.
