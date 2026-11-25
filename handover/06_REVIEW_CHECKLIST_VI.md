# Checklist đánh giá độc lập

Đây là rubric đề xuất để reviewer đánh giá, không phải điểm tự chấm. Mỗi hạng mục kết luận PASS / PARTIAL / FAIL / BLOCKED / NOT APPLICABLE kèm file:line, commit, command, output hoặc nguồn độc lập. Không suy điểm tiến độ từ số file hay số test. Một critical gate fail không được bù bằng điểm phần khác.

| Hạng mục | Điểm tối đa | Yêu cầu |
|---|---:|---|
| Mục tiêu & scope | 10 | Dự báo lịch sử xác suất, không nhầm paper/live hoặc backtest odds |
| Provenance, quyền, hash | 15 | Raw/derived pins, source attribution, source drift, quyền sử dụng |
| Data quality & identity | 15 | Kiểm tra event/tier/round, duplicate, missing IDs, official draw gap |
| Temporal integrity | 20 | Freeze trước event, 28-day lag limitation, no current-match/after-event information, no future labels |
| Experimental design | 15 | Baseline, matched cohorts, calibration separate, out-of-time vs inspected development |
| Reproducibility & engineering | 15 | Full CI, exact revision, test robustness, code readability, reproducibility, version control |
| Uncertainty & honest conclusions | 10 | Brier/LL, event-cluster CI, coverage, no cherry-picking, limits |
| Tổng | 100 | Chỉ chấm các hạng mục có bằng chứng |

## Required critical gates
- [ ] Source bytes exactly match SHA256; no silent substitution, no raw redistribution, rights scope respected.
- [ ] Source candidate and official certification remain separate; no fabricated canonical match ID or official draw completeness.
- [ ] Every feature has explicit availability cutoff; no same-event results or future result leakage. Examine embargo as assumption, not verified match timing.
- [ ] Disjoint fit/calibration/evaluation; no claim 2023–25 untouched. No threshold tuning on declared test.
- [ ] Baseline scores and matched cohort independently reproduced or discrepancy documented.
- [ ] Source/derived manifest, code commit, environment and scripts traceable.
- [ ] Model trust and allocation false; stake zero; no ROI/CLV claims.
- [ ] Reviewer explicitly marks unfinished work and excludes unsupported assertions.

## Kiểm tra code độc lập
Inspect all core modules and tests. Check schema equality, source byte cap, duplicate equivalence excludes only match_num, conflicts quarantine all rows, exact source level-A exception, canonical event date grouping, same event batch state, identity orientation, missing surface history, denominator alignment, log loss clipping, bootstrap grouping, calibrated output and split leakage. Test adversarial fixtures rather than only happy path. Verify historical default still unchanged. Distinguish old research_train generic pipeline from new locked source-specific pipeline. Inspect 5 diverged PR diffs and integration #31; no automatic equivalence.
 
## Kết quả reviewer cần bàn giao
1. Executive verdict + scope evaluated.
2. Score table with evidence and reason per item.
3. Critical defects, reproducible steps, expected/observed.
4. Findings prioritized P0/P1/P2, file and line references, recommended repair and acceptance tests.
5. Unresolved provenance/official draw/chronology/rights; state whether source-dependent check blocked.
6. Rerun log and dependency freeze; no raw provider rows in public review.
7. Go/no-go separately for offline exploratory research, independent evaluation, and any production readiness. Current handover does not authorize deployment.
