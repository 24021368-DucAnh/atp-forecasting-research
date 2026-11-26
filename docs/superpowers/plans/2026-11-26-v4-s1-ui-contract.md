# S1 Task 2 execution contract

Task 1 GREEN verified on exact 9be6a12d84a193fae1ca33403fc5fbea2a1af3e9:
run 45781012398, each of four jobs 657 tests/266 hashes and 11/11 steps.
Windows checkout LF pin fixes digest without altering evidence or reader.

Task 2 tests: actual Streamlit AppTest on Python 3.11 Ubuntu and Windows.
Separate workflow only on relevant pull requests, read-only permissions; no
change to existing four CI checks, branch rules, scheduled workflows or V3
dependency locks. UI tests are explicitly skipped in core CI if Streamlit is
absent, but import is mandatory in dedicated V4 CI. Direct dependency pins
are not a full transitive lock. Capture full environment locks by S7.

RED first: test_dashboard.py covers overview verified values/18 candidates,
read-only model selection, five locked pages and missing/tampered evidence.
Expected 9 failures for absent dashboard/app.py on both OS jobs, not an
installation failure. After actual RED, implement only the offline UI and
local launch docs, then verify both UI jobs and four existing checks.
Dashboard never accesses network/data sources or training, shows unavailable
rather than fabricated live counts. No fake fixtures. Manual browser visual
and accessibility review and real Windows launcher smoke still required for
S1 acceptance; AppTest does not replace them. No automatic merge.
