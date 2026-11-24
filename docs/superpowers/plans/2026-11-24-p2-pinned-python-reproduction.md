# P2B.1 Pinned Python Reproduction Plan

**Goal:** reproduce the existing retrospective skill study on exact historical bytes.
**Architecture:** isolated test harness fetching fixed Git blob objects; existing CLI unchanged; aggregate-only output.
**Tech stack:** Python 3.11 stdlib, existing atp_gate package, one-off GitHub Actions.
**Spec:** docs/superpowers/specs/2026-11-24-p2-pinned-python-reproduction.md

- [ ] Pin five recorded source blob hashes and implement a bounded verification harness.
- [ ] Run the existing CLI unchanged with fixed defaults on the verified bytes.
- [ ] Compare the observed sample counts and metrics, report discrepancies without adjusting parameters.
- [ ] Verify the actual job log, record evidence in issue #29 and preserve the no-market/no-allocation boundary.

