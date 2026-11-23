# P1.4d — Historical Correction Source Intake (Fail Closed)

**Goal:** Evaluate provenance and rights-review *of one proposed local artifact* without inventing February 2024 ATP results or enabling a model.

## Existing data blockers
The pinned Valuebetennis 2024 export lacks all February-dated rows. The older February 2024 HTML tournament index supplies twelve event IDs but **no licensed match-level evidence**, verified ATP main-draw completeness or executable T−60 price. Those gaps cannot be repaired by re-labeling an index, downloading a mirror with different terms, or filling missing outcomes with guesses.

## Local, read-only CLI

```bash
python -m atp_gate historical-source-intake \
  /path/to/authorized-feb2024-export.csv \
  /path/to/intake-manifest.json \
  reports/valuebetennis_tournaments_2022_2026.json \
  docs/registries/atp_2024_february_official_events_v1.json \
  --out reports/feb2024_source_intake.json
```

The command hashes the **original bytes** of the artifact and inventory, checks declared source size, metadata, official-event keys and permission report hash syntax. It does not change the input files, download anything, parse match outcomes or infer a valid draw.

### Manifest example (illustrative, NOT a grant of rights)

```json
{
  "version": "P1_AUTHORIZED_SOURCE_INTAKE_1",
  "inventory_sha256": "<sha256 of exact pinned inventory bytes>",
  "source": {
    "name": "provider-authorized-2024-02.csv",
    "sha256": "<sha256 of exact local CSV bytes>",
    "size_bytes": 123456,
    "source_url": "https://provider.example/authorized-export.csv",
    "retrieved_at_utc": "2026-11-24T00:00:00Z",
    "format": "CSV",
    "row_count_claimed": 100
  },
  "scope_event_keys": ["ATP_2024_ROTTERDAM", "ATP_2024_DALLAS"],
  "permission": {
    "scope": "2024_FEB_MATCH_LEVEL_EXPORT",
    "evidence_url": "https://provider.example/explicit-reuse-agreement",
    "report_id": "independent-rights-review-id",
    "report_sha256": "<sha256 of independent rights review>",
    "ai_training_allowed": true,
    "commercial_use_allowed": true
  },
  "draw_review": {
    "report_id": "independent-draw-review-id",
    "report_sha256": "<sha256 of independent draw review>",
    "verified_official_match_ids": false,
    "complete_main_draw": false
  }
}
```

Replace all placeholders only when actual evidence exists; do not create purported approval reports or source rows to make validation pass. Real downloads may use an entirely different field schema. A row-count **claim** is metadata, not verified row count; the byte SHA/size alone do not prove data accuracy.

### Permission review
- The normal CLI intentionally has **no switch to self-approve rights**. It always reports `NO_AUTHORIZED_HISTORICAL_REPAIR_SOURCE` until a separate independently managed trusted report registry is integrated.
- The Python API `audit_source_intake(... trusted_permission_reports={report_id:sha256})` permits an external *trusted* reviewer to identify a rights-review artifact, but even then it reports only `SOURCE_PERMISSION_REVIEWED_MATCH_AUDIT_PENDING`. It must not be wired to training eligibility without inspecting actual permission documents and the legal scope.
- A provider's published CC BY notice for **downloadable CSVs** does not automatically apply to unrelated legacy HTML match pages.
- Rights check must also consider noncommercial restrictions and restrictions on model training or commercial reuse, without relying solely on publicly reachable URLs.
- The trust mapping authenticates the **review report identity** only if the caller itself protects that mapping. It is not a legal opinion or a cryptographic source-signature scheme.

### Readiness remains blocked
All outputs state:
```json
{
  "mode": "HISTORICAL_RESEARCH_ONLY",
  "event_identity_verified": false,
  "main_draw_verified": false,
  "t60_quote_verified": false,
  "eligible_for_model_training": 0,
  "live_eligible": false,
  "allocation_enabled": false,
  "stake": 0
}
```

A licensed source is only the **start** of P1.4d, not proof of correct players, rounds, retirements, schedule times, outcomes or bookmaker odds. Complete official draw / stable player identity reconciliation, source corrections, chronological model validation, and independently timestamped price evidence are separate phases.

**Review links:** [P1.4d #17](https://github.com/24021368-DucAnh/atp-forecasting-research/issues/17), [P1.4 #11](https://github.com/24021368-DucAnh/atp-forecasting-research/issues/11), [P2 #12](https://github.com/24021368-DucAnh/atp-forecasting-research/issues/12), [P3 #13](https://github.com/24021368-DucAnh/atp-forecasting-research/issues/13).
