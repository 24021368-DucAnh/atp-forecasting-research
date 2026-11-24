# TML 2025 Revision Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox syntax for tracking.

**Goal:** Check whether the actual publisher revision supplies the missing 2025 match numbers.
**Architecture:** Isolated research script; existing verified Git blob fetch and local snapshot updater; exact-key aggregate comparison; no production changes.
**Tech Stack:** Python 3.11, csv, collections, existing atp_gate, GitHub Actions.
**Spec:** docs/superpowers/specs/2026-11-24-tml-2025-revision-audit.md

- [ ] Add deterministic comparison fixture and verify RED.
- [ ] Implement aggregate-only comparison and verify synthetic tests.
- [ ] Run one-off publisher HTTPS retrieval and comparison; preserve provenance and evidence.
- [ ] Record actual findings and next action in Issue #29; do not certify official identity or model performance.

