# TML 2025 Revision Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox syntax for tracking.

**Goal:** Check whether the actual publisher revision supplies the missing 2025 match numbers.
**Architecture:** Isolated research script; existing verified Git blob fetch and local snapshot updater; exact-key aggregate comparison; no production changes.
**Tech Stack:** Python 3.11, csv, collections, existing atp_gate, GitHub Actions.
**Spec:** docs/superpowers/specs/2026-11-24-tml-2025-revision-audit.md

- [x] Add deterministic comparison fixture and verify RED.
- [x] Implement aggregate-only comparison and verify synthetic tests.
- [x] Run one-off publisher HTTPS retrieval and comparison; preserve provenance and evidence.
- [x] Record actual findings and next action in Issue #29; do not certify official identity or model performance.


## Execution evidence
- RED #45357174038 missing module; GREEN #45357267968 six tests and real provider HTTPS comparison.
- Additional RED #45357427874 (1 failed, 6 passed) for missing segmentation; GREEN #45357509313 (7 passed, source comparison success) at 7ab2018.
- Provider revision SHA256 5ccf52d912085d6a5ba3effdc5f2f216f170aabfd8850086b5f92c7ccedfd53e. 2,943 rows, zero missing match numbers/malformed rows/duplicate numbered groups. 394 candidates with unchanged core; 95 change only tourney_date, all event 2025-5014. 43 numbered rows change core, including 27 surfaces. See V2 evidence JSON.
- Ruling: keep pinned new source hash, avoid documentation-only repeat downloads. The Shanghai official main draw schedule is Oct 1–12; old provider date Sep 24 inconsistent with that definition. Exact revised provider date not exported; do not infer it. Official draw certification still false.
- Ruling: this is source comparison completion only, not official source acceptance. Next verify chronology and surface mappings against primary references before preregistered baseline sensitivity analysis. No independent reviewer available; self-review only. No changes to allocation or forecast policy.
