# P0.25b.2 Research Evidence Archive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Preserve and independently re-read the exact inputs of the synthetic cash-history audit.
**Architecture:** Typed JSON envelope, SHA256 address, local atomic no-overwrite publication, strict verification using existing audit.
**Tech Stack:** Python 3.11+, stdlib, Pydantic, pytest.
**Spec:** docs/superpowers/specs/2026-11-24-paper-evidence-archive.md.

## Global constraints
Private research only; no transfers, market access or allocation changes. A digest is not proof of external authenticity. Require local filesystem hard-link support.

## Tasks
- [ ] Add tests for storage, idempotence, tampering, invalid snapshot, path traversal, duplicate keys and size bound.
- [ ] Observe RED before implementation.
- [ ] Add minimal store/verify module, bounded reads and atomic publication.
- [ ] Run full Windows/Ubuntu matrix, review and record results; update Issue #25. Do not merge without independent review.

