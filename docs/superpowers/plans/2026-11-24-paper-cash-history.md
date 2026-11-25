# P0.25b.1 Paper Cash History Implementation Plan

> For agentic workers: use superpowers:executing-plans and test-driven-development.

**Goal:** Reconcile complete paper-only cash evidence independently of current balance snapshots.

**Architecture:** Separate typed opening/close evidence envelope; immutable original match journal; pure replay and external digest comparison.

**Tech Stack:** Python 3.11+, Pydantic, Decimal, hashlib, pytest.

**Spec:** docs/superpowers/specs/2026-11-24-paper-cash-history.md.

- [ ] RED: add tests for 1000 opening, 10 loss, 10 hypothetical topup, carried 10, 19 win payout, 9 withdrawal, and state tampering. Cover chronological, hash and missing evidence failures.
- [ ] Observe RED via CI.
- [ ] GREEN: implement strict independent replay, close evidence helper and canonical hash in src/atp_gate/paper_cash_history.py. Keep old ledger interface and policy unchanged.
- [ ] Verify full CI, inspect diff and update issue #25 with limitations. Independent review and eventual merge remain separate.
