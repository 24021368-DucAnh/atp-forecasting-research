# V4 S8 Multi-source Incremental Intake Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Build a source-agnostic, incremental, auditable ATP intake without rewriting the accepted offline system.

**Architecture:** Policy-gated adapters feed immutable local observations; normalize, reconcile and quarantine before a separate real-research database can consume records. Preserve S1–S7 synthetic schema and V3 research. Stage 0 is a documentation/preflight proposal, not activation.

**Tech Stack:** Python 3.11/3.12, SQLite, stdlib HTTPS/CSV/JSON/hashlib, existing pytest and Windows worker lease. No new dependency without separate justification.

**Spec:** docs/superpowers/specs/2026-11-28-v4-s8-multisource-design.md.

## Global constraints
- Read accepted main, binding V4 spec and current docs before each stage.
- Native single-writer workflow; batch related tests and implementation into coherent RED/GREEN units, use local tests where possible.
- Preserve 347 baseline manifest pins except explicitly approved V4 integration. Never alter V3 or accepted synthetic DDL to admit real data.
- All network disabled by default; no arbitrary URL or HTML crawler. No new source fetch before source-specific rights and owner receipt.
- No raw vendor data, credentials or private observations committed to public GitHub. No paid purchase, real fit, scheduler, export or promotion.
- Scope below is proposed, pending owner review; real schema and provider adapters need actual approved schema samples, not guessed fields.

## Review focus
- Unknown/expired policy or redirected host: zero unauthorized calls.
- Same snapshot/hash or revised observation: no duplicate canonical match, no loss of old evidence.
- Mismatched source identity / shared upstream: quarantine, not majority vote.
- Missing start/publication or provider clock versus local observed: never fabricate chronology or score.
- Interrupted write, wrong mode, restart and failed backup: no partial real or synthetic contamination.

### S8.0 — Offline source registry and policy contracts (first coding unit, proposed)

Files: create src/atp_lab/intake/policy.py, src/atp_lab/intake/__init__.py, tests/v4/test_intake_policy.py.
Interfaces (proposed): immutable SourcePolicy and ApprovalReceipt; check_request(policy, receipt, request, *, now) -> Decision; pure function, no transport import. Decision allowed, reason. Deny by default; typed scope, allowlisted origin/path and operations, normalized UTC, expiry and exact receipt digest. Approval is local policy evidence, not third-party authority.
- [ ] RED tests: discovery-only/expired/revoked/unknown source, wrong origin/method/operation, malformed timestamps/receipt, approved exact matching synthetic receipt; assert denied cases never call transport (injected spy).
- [ ] Run pytest tests/v4/test_intake_policy.py -q and record intended RED.
- [ ] GREEN implement minimal immutable decision and receipt validation; real authorization creation unavailable; only synthetic test receipts used.
- [ ] Run focused tests, full pytest -q, manifest and dependency checks; independent review and owner exact-head approval.

### S8.1 — Offline observation/reconciliation contracts (after S8.0 accepted)

Files (proposed): src/atp_lab/intake/observations.py, reconciliation.py, tests/v4/test_intake_observations.py, tests/v4/test_intake_reconciliation.py.
Interfaces: immutable Observation with source_id, endpoint_id, payload_sha256, observed_at, optional provider_event_at/available_at, schema_version; reconcile(observations, crosswalk) -> decision with evidence IDs and explicit reason. Use bounded content-addressed store with verified atomic publication, explicit source revision linkage. Unknown provider clocks stay null. Separate test namespace and isolated store; no real data or migration of synthetic DB.
- [ ] RED: same hash replay, correction, conflicting IDs/winners, shared upstream, missing timing, partial export, corrupt content, interruption, unsafe path, wrong DB mode.
- [ ] GREEN implement offline receipt storage and deterministic fail-closed reconciliation with fictional inputs; independent test cases for source-specific alias versus canonical ID, partial export does not imply deletion.
- [ ] Run focused tests then full pytest -q, check backup/restart and unchanged S1–S7; independent review and exact-head acceptance.
- [ ] Only after approved source schemas, propose exact real-research DDL and adapters in a separate plan. Do not rename SYN IDs or relax v2–v5 synthetic constraints.

### S8.2 — Source-specific eligibility and bounded dry run (BLOCKED on prerequisites)

- [x] Verify main checkpoint and read S3/S7 and P1.5 contracts; identify existing TML updater.
- [x] Review public source documentation and record source capability inventory in spec; no real match payload fetched.
- [ ] Source-specific written evidence of rights and restrictions, permissible operations and retention; independent review of upstream and timestamp semantics.
- [ ] Obtain owner-approved exact source endpoints, intended usage, rate/byte/time budget, dry-run event and separate private destination. Paid plans need quote and purchase approval.
- [ ] Define adapter from approved schema, RED/GREEN with fictional payloads and no real network in CI. Verify policy gate before every request/redirect, no credentials in logs, counters include retries, bounded read and atomic receipts. Reuse P1.5 current-season snapshots if separately authorized; do not invoke force or schedule.
- [ ] After exact-head acceptance and explicit dry-run authorization, perform one manual bounded dry run locally, document coverage, identity, conflicts, timestamp semantics, actual clock evidence and cost. Quarantine unsupported rows. No fabricated validation or live prediction.

### S8.3 — Real integration/parity and sequential evaluation (BLOCKED)

- [ ] Propose separate real warehouse schema and narrowly scoped migration after accepted dry-run evidence; verify backup and worker isolation.
- [ ] Validate canonical identities, event/fixture/result revision coverage and real point-in-time feature parity using approved inputs; retain source and time lineage; historical data lacking valid times cannot count as prospective skill.
- [ ] Freeze prospective protocol and approval; test actual-start, result visibility, correction, missing data and matched fixed cohort; require owner exact-head acceptance.
- [ ] Separate decisions for model fit/persistence and optional local scheduler; no automatic production promotion or reopening historical test data. Source quality/readiness shown through existing dashboard, with explicit blocked states.

## Current checkpoint

Design/plan and public documentation review complete as a proposed
docs-only deliverable. No product code, CI claim, data collection,
external account or scheduler change. Review scope and owner approval
before coding. Source activation remains separately locked.
