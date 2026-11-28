# V4 S8.0/S8.1 offline intake contracts

Status: implemented on a review branch, full repository acceptance pending.
Owner approved design and implementation of both offline units, not real
activation or merge. S1-S7 and V3 remain unchanged.

## Interfaces

- `atp_lab.intake.policy`: pure synthetic policy and receipt validation,
  exact source, HTTPS test endpoint, operation, method, canonical UTC
  clock, expiry, caller-supplied synthetic request budget, and SHA256
  receipt binding. `invoke_fake` accepts only a trusted injected test
  double for the fictional domain. It is not a general transport or
  permission service; no runtime network client, persisted quota counter,
  or real approval issuer exists.
- `atp_lab.intake.observations`: use a new, explicitly chosen, absolute
  local directory named `synthetic_intake`. The marker identifies a
  separate fictional ledger; accepted SQLite stores are untouched.
  A maximum of 4096 receipts, 1 MiB per payload. A verified blob is
  published before a no-clobber immutable receipt. Exact replay and later
  observation of unchanged revision preserve the original first-seen
  receipt. Changed revisions link to their predecessor; missing links
  fail inventory validation. Interrupted publication may leave an
  unreferenced blob; it never becomes a visible observation without
  a verified receipt. Trusted local single writer and a filesystem
  supporting same-directory hard links are required. Back up the
  quiescent directory as a unit and verify inventory on restore.
- `atp_lab.intake.reconciliation`: deterministic reconciliation of one
  fictional canonical match from retained full observation history and
  explicit aliases. Different provider identities are not auto-merged.
  Same source or shared upstream is not independent corroboration.
  Missing revision, outcome, identity, scope and timing conflicts do not
  score; quarantine preserves supplied evidence IDs. No deletion inferred
  from an omitted row. Timing-complete corroboration is synthetic only.
  Evidence IDs are caller-supplied references; future authorized adapters
  must verify linkage to immutable raw receipts before real use.

The S8 observation `available_at` denotes a claimed provider availability
clock, not a local post-ingest availability clock. It can be null; if
provided it cannot follow the local receipt. No clock is invented.
S4/S5 actual real timing, identity and prospective eligibility remain
separate gates. No reconciliation decision permits scoring.

## TML reuse and deferred work

Keep P1.5 `src/atp_gate/tml_snapshot.py` and its existing tests unchanged.
The existing updater is an input candidate for S8.2; do not call it, its
force option or the Windows daily script from the offline contracts. Do
not import its data or invent its schema mapping. Provider-specific
adapters, actual terms/rights receipts, real schema, operational quota
tracking, network redirect checks, provenance binding to provider bytes,
local scheduling and real parity are deferred to source-specific approval.
The public repository contains only code, public-source references and
fictional tests; no vendor payloads or credentials.

## TDD execution ledger

Baseline: design PR #74 at 23adb5775ad0bc1aafb6f137bd2584a331ffab2a;
accepted main c66847471d2cc61241700f223b91c5e3d2cdc4d5.
Local git clone/ls-remote failed due to DNS; isolated workspace with
only new modules and tests used for focused test runs. GitHub connector
for exact-byte commits; full matrix must be verified separately.
- Initial RED: 48 tests failed due to missing modules.
- Initial GREEN: 48 passed.
- Self-review RED: 4 failures, 48 pass (missing predecessor, same-source
  aliases, missing quarantine evidence IDs, missing revision).
- Remediation GREEN: 52 passed, focused pytest, no network.
- Ruling: batch both approved offline tasks behind one draft PR; preserve
  test-only commit as parent of implementation, with one branch push
  for regression. This is not separate stage acceptance or a merge.
- Ruling: use a separate file ledger instead of altering synthetic SQLite
  schema; validate full revision chains during inventory. No real DB or
  persistent quota service. Test-only transport does not authorize network.
- Ruling: retain claimed provider availability separately from local
  observation. Distinct synthetic upstream IDs are not proof of actual
  source independence. No scoring or training even when all clocks exist.
- Ruling: preserve all P1.5 and S1-S7 pins; reuse TML at a later authorized
  boundary rather than reimplement the downloader or execute it now.
- Review: author self-review only. Independent review or explicit waiver,
  exact-head merge approval, and postmerge verification are required.

Focused run: `PYTHONPATH=src python -m pytest -q tests/v4/test_intake_policy.py tests/v4/test_intake_observations.py tests/v4/test_intake_reconciliation.py`.
