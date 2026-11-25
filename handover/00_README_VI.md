# ATP Selective Forecasting — Bàn giao đánh giá độc lập
**Ngày chốt:** 25/11/2026 · **Mốc kỹ thuật:** P1.8c · **Package metadata:** 0.2.1 (không phải release production).

## 1. Phạm vi và nguồn gốc
Repository: https://github.com/24021368-DucAnh/atp-forecasting-research
Checkpoint gốc (toàn bộ 189 file, 1.082.675 byte): `2e084eedfc44c8ffaabd1fc5cbfb00769b703574`.
Nhánh bàn giao chỉ bổ sung thư mục `handover/` và không sửa mã, dữ liệu, test hoặc tài liệu gốc. Main tại lúc lấy snapshot: `d64fdb23a668bde5168d5dd61809edc16ecd3c29`. Không merge, không đổi trạng thái PR.
Phạm vi được xác định trong [Issue #29](https://github.com/24021368-DucAnh/atp-forecasting-research/issues/29): dự báo kỹ năng lịch sử offline, nghiên cứu cá nhân phi thương mại. Không odds thực thi, stake, ROI, CLV, hoặc chứng nhận mô hình/khả năng thương mại. Tất cả nguồn chưa được chứng nhận đầy đủ; dữ liệu bên thứ ba tải trực tiếp từ nhà cung cấp theo quyền sử dụng, không có CSV gốc trong gói.

## 2. Thứ tự đọc và bộ tài nguyên
| File | Nội dung |
|---|---|
| [01_ARCHITECTURE_AND_STATUS.md](01_ARCHITECTURE_AND_STATUS.md) | Mục tiêu, kiến trúc, giai đoạn, trạng thái và giới hạn |
| [02_REPRODUCE_VI.md](02_REPRODUCE_VI.md) | Windows/Linux, test, tái lập và xử lý drift |
| [03_SOURCE_REGISTER.json](03_SOURCE_REGISTER.json) | Nguồn gốc, Git blob, SHA256, manifest, quyền và tham chiếu |
| [04_EXECUTION_EVIDENCE.json](04_EXECUTION_EVIDENCE.json) | Kết quả CI, run IDs, metrics, manifest và evidence |
| [05_REPOSITORY_SNAPSHOT.json](05_REPOSITORY_SNAPSHOT.json) | Issues, PR bodies, head/base, quan hệ ancestry, main |
| [06_REVIEW_CHECKLIST_VI.md](06_REVIEW_CHECKLIST_VI.md) | Rubric, kiểm tra độc lập và tiêu chí go/no-go |
| [07_REVIEW_PROMPT_VI.md](07_REVIEW_PROMPT_VI.md) | Prompt giao cho người/AI đánh giá |
| [08_ORIGINAL_TREE.json](08_ORIGINAL_TREE.json) | Danh mục 189 file nguồn, kích thước, Git blob hash |
| [09_DOCUMENT_INDEX.md](09_DOCUMENT_INDEX.md) | Liên kết 95 tài liệu nguồn trong repo |
| [10_verify_original_tree.py](10_verify_original_tree.py) | Công cụ kiểm tra file gốc theo Git blob SHA1, tạo SHA256 local |

## 3. File gốc trong gói
`README.md`, `pyproject.toml`, `src/atp_gate/` (32 file), `tests/` (35 file), `scripts/` (11 file), `.github/workflows/` (9 file), `docs/` (95 file), `examples/` (3 file tổng hợp), `MANIFEST_SHA256.txt`, `.gitignore`. Ví dụ synthetic không phải dữ liệu thật. Manifest SHA256 lịch sử có thể không bao phủ checkpoint hiện tại; dùng danh mục mới để kiểm tra đầy đủ.
Dữ liệu riêng trên máy người dùng, local reports, weights chưa commit, credential/token, và bản ZIP đời trước ngoài repo không được coi là có trong gói. Cần chủ sở hữu đối chiếu nếu có thêm tài nguyên chưa commit. Không cấp quyền repo cho bên ngoài từ gói này; giữ quyền truy cập phù hợp.

## 4. Kết quả đã xác minh
Final CI [45539495569](https://github.com/24021368-DucAnh/atp-forecasting-research/actions/runs/45539495569): Ubuntu/Windows × Python 3.11/3.12 đều 411 passed, ABSTAIN, stake 0. Actual locked cohort replay [45539306618](https://github.com/24021368-DucAnh/atp-forecasting-research/actions/runs/45539306618): 12.620 eligible, 7.694 evaluated (2.600/2.647/2.447). Global LL 0.6300670180626626, Brier 0.22063010972181757; Surface LL 0.6320572443209497, Brier 0.2211424236796862. Coinflip LL 0.6931471805600358, Brier 0.25. 2023–25 are previously inspected development years; no untouched prospective set.

## 5. Cách sử dụng
1. Download ZIP commit bàn giao bằng tài khoản có quyền hoặc clone repo và checkout đúng checkpoint.
2. Đọc tài liệu trạng thái, quyền nguồn và checklist; chạy verifier trước cài đặt.
3. Chạy pytest; sau đó chạy replay thật nếu có quyền nguồn và đúng SHA.
4. Ghi kết quả đánh giá độc lập, lỗi và hạn chế; không sử dụng báo cáo này như chứng nhận chính thức.

**Quyết định bàn giao:** thêm nhánh handover riêng, không làm thay đổi branch nghiên cứu. Không tự nhận đã kiểm toán toàn bộ code, lịch sử Git, bí mật hoặc license. Git tree là bằng chứng danh mục, CI là bằng chứng chạy test; reviewer độc lập vẫn cần thiết.
