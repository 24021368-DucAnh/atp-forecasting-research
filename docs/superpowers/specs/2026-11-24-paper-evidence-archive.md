# P0.25b.2 — Private synthetic research evidence archive

Purpose: preserve reproducible evidence for the P0.25b.1 internal cash consistency audit. No live activity, payments, odds collection, selection policy changes or externally authenticated proof.

Alternative designs: mutable latest JSON loses prior evidence; hash-only report cannot reconstruct inputs. Selected: local content-addressed complete JSON envelope, validated by the existing audit, with exact original byte digest retained by the owner separately.

API in paper_evidence_archive.py:
- store_cash_evidence(root, book, opening, closes, as_of) -> dict: validate the existing cash-history audit; serialize typed evidence and snapshot into versioned UTF-8 JSON; hash exact bytes; publish <sha256>.json using an atomic no-overwrite link from a same-directory temporary file. Repeated identical bytes are idempotent. Existing incorrect bytes at that filename fail closed. No index/pointer updates, no network.
- verify_cash_evidence(root, expected_sha256) -> dict: require exactly lowercase 64 hex characters; read at most 16 MiB; compare exact original bytes to caller-supplied digest before parsing; reject duplicate JSON keys, unknown envelope fields, malformed schema, missing evidence and invalid cash replay. No inferred historical records.
- Archive digest is distinct from the canonical cash-history evidence digest. Full archive includes the snapshot and explicit as-of clock; cash-history digest excludes the mutable snapshot. The caller must retain a trusted digest separately; matching bytes do not prove source authenticity. Always external_authenticity_verified=false, allocation_enabled=false and stake=0.
- Only private local files. No raw provider dataset or network. No claim of filesystem immutability, signatures, cross-machine persistence or external authenticity. Symlink entries are refused; root is a trusted owner-controlled directory, not a hostile multiuser filesystem. Atomic hard-link publication requires supporting local filesystem; failures must surface rather than silently overwrite. Limit read/write bytes to 16 MiB.

Tests: round-trip and idempotence, distinct snapshots, altered file, incorrect expected digest/path traversal, invalid snapshot before write, symlink rejection where supported, malformed duplicate-key JSON, oversized input. TDD plus full four-job CI. Stacked on PR #33; independent review remains mandatory.
