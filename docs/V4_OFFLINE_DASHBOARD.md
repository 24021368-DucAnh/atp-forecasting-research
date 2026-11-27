# V4 offline dashboard

The dashboard provides six read-only local research pages: Overview,
Upcoming, Tournaments, Results, Model Lab, and Data Health. Historical mode
shows only the exact hash-verified P2.4 development evidence. Synthetic Demo
mode reads only the local SQLite snapshot and clearly identifies fictional
records. Upcoming rows show fixture state; cancelled and postponed fixtures
cannot appear as ordinary committed forecasts. Results labels commitments
and assessments only when their S5 receipts verify. Legacy rows without valid
receipts remain visible as `UNVERIFIED`, with probability and outcome evidence
withheld. Each assessment shows the result revision it assessed and the latest
stored result revision/state; an assessment for an older revision is labelled
`HISTORICAL` without changing its immutable receipt. Overview counts are
stored-row counts and may include legacy entries.

The dashboard does not fetch data, write the database, train models, start a
worker, schedule jobs, or activate candidates.

Windows setup, launch/stop/status, explicit demo initialization, verified
backup/restore, locked dependencies, and manual acceptance steps are in
[V4 S7 local deployment](V4_S7_LOCAL_DEPLOYMENT.md).
