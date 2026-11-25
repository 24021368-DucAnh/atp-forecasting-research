# Hướng dẫn tái lập và kiểm chứng

## Điều kiện
Python 3.11 hoặc 3.12, mạng cho cài dependencies và phép truy cập nguồn. Gói bàn giao chứa code tại `2e084eedfc44c8ffaabd1fc5cbfb00769b703574` cùng tài liệu mới trong handover/. Nếu clone riêng để tái lập code gốc:
```bash
git clone https://github.com/24021368-DucAnh/atp-forecasting-research.git
cd atp-forecasting-research
git checkout --detach 2e084eedfc44c8ffaabd1fc5cbfb00769b703574
```
Nếu dùng ZIP bàn giao, giải nén và đứng tại thư mục có pyproject.toml. Không chạy git pull main thay cho checkpoint.

## Kiểm tra toàn vẹn gói
Từ thư mục gốc ZIP bàn giao:
```bash
python handover/10_verify_original_tree.py
```
Verifier so sánh 189 file gốc theo size + Git blob SHA1 (header `blob <len>\0`), xuất danh sách SHA256 thực tế vào `handover/VERIFIED_SHA256_LOCAL.txt` khi tất cả đạt. Trên checkout Git có auto-CRLF, kiểm tra code gốc từ archive hoặc clone với `git -c core.autocrlf=false clone ...`; không tự sửa nội dung để ép hash khớp. File handover không nằm trong original inventory.
Không coi MANIFEST_SHA256.txt đời trước là danh mục mới. Gói này không phải signed release.

## Windows PowerShell
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[test,ml]"
.\.venv\Scripts\python.exe -m pip freeze > environment-local.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m atp_gate evaluate examples/synthetic_unvalidated.json
.\.venv\Scripts\python.exe -m atp_gate research-audit examples/research_synthetic.csv
```
## Linux/macOS shell
```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[test,ml]"
python -m pip freeze > environment-local.txt
python -m pytest -q
python -m atp_gate evaluate examples/synthetic_unvalidated.json
python -m atp_gate research-audit examples/research_synthetic.csv
```
Kỳ vọng 411 passed; safe default gate ABSTAIN / stake=0. Python 3.11/3.12 Windows/Ubuntu CI xác minh; macOS chưa xác minh. Không nói dependency versions được khóa hoàn toàn: pyproject dùng version ranges.

## Thực nghiệm dữ liệu thật (chỉ khi được phép)
Đọc `03_SOURCE_REGISTER.json`, docs/TML_NONCOMMERCIAL_RESEARCH.md, docs/DATA_SOURCE_DECISIONS.md. Các script nguồn sử dụng GitHub Git blob API và publisher endpoint, kiểm tra source SHA và sử dụng temporary directory; không commit dữ liệu gốc.
```powershell
.\.venv\Scripts\python.exe -m scripts.p1_8c_cohort_research
```
Linux:
```bash
python -m scripts.p1_8c_cohort_research
```
Nếu endpoint 2025 đổi SHA256: fail closed. Không bỏ kiểm tra SHA, không thay thế bytes mới và không quảng bá replay sai. Cần exact authorized local version từ kho riêng của chủ sở hữu; script hiện tại tải trực tiếp endpoint, chưa có tùy chọn CLI local override cho revised 2025. Có thể kiểm chứng code/CI/aggregate bằng chứng gốc trong lúc chưa tái lập được live download; ghi BLOCKED_BY_SOURCE_VERSION_DRIFT.
Expected manifest SHA256 `b9b55b6c75f1f43394b3e69d19c6b791faedc8539908608ecf1d74dfaabcb8fb` (JSON canonical as implemented). Expected 12,620 eligible; 7,694 evaluated; 2023=2600/2024=2647/2025=2447. Global LL 0.6300670180626626, Brier 0.22063010972181757. Surface LL 0.6320572443209497, Brier 0.2211424236796862. Expected reference score tolerance 1e-12. Original input and derived SHA must match all five seasons.
Earlier studies (separate cohorts, do not compare without reconciling): `python -m scripts.reproduce_pinned_tml_elo`, `python -m scripts.p1_7c_level_a_research`, `python -m scripts.p1_8a_identity_research`, `python -m scripts.p1_8b_duplicate_research`. Read code and docs before executing network access. Do not upload source rows or private outputs.

## Kiểm tra PR/CI
Open original repo issues and PRs from 05_REPOSITORY_SNAPSHOT.json. Five PR heads diverged from current checkpoint, not proof of missing code: review diff and exact commit, never auto-merge. Final CI https://github.com/24021368-DucAnh/atp-forecasting-research/actions/runs/45539495569; actual cohort replay https://github.com/24021368-DucAnh/atp-forecasting-research/actions/runs/45539306618. If logs expired use committed reports and snapshot evidence with explicit limitation. Record command, exit code, Python/platform, pip freeze, input SHA, output, and discrepancy.
