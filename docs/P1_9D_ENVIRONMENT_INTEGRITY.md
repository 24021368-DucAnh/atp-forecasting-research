# Environment and repository integrity (P1.9d)

Use the appropriate version-pinned runtime/test/ML dependency list in requirements/ (Ubuntu or Windows, Python 3.11 or 3.12). These exact package versions were observed in successful P1.9c CI run 45545970390. Not cryptographic wheel hashes, OS images, pip/build-tool versions or a complete offline wheelhouse. Existing historical workflow files remain as historical evidence; main CI uses the locks. Run from a clean virtual environment:

```bash
python -m pip install --no-deps -r requirements/ubuntu-latest-py3.11.txt
python -m pip install --no-deps -e ".[test,ml]"
python -m pip check
python -m pytest -q
```

Use windows-latest-py3.11.txt or the matching Python 3.12 file when appropriate. Package metadata still declares Pydantic for the gate; research module imports and CLI help no longer eagerly import it. Public gate exports are lazy and compatible; evaluating without gate dependencies fails closed.

Root MANIFEST_SHA256.txt covers all regular tracked Git index blobs except itself. No ignored/untracked data, no source CSV redistribution. Generate only after staging changes:
```bash
git add <intended paths>
python -m scripts.repository_manifest generate
git add MANIFEST_SHA256.txt
python -m scripts.repository_manifest verify
```
The verifier uses canonical Git blob bytes (rather than platform-specific working-tree line endings) and rejects dirty tracked files. Requires a Git checkout, not an extracted archive. The manifest is not a signature. Preserve old manifest in Git history; no self hash.

Main at 6d6faf81 had 195 files vs verified P1.9c 202: seven missing, three changed, no main-only paths. Main CI 45549473316 passed 428 tests, omitting eight P1.9c tests. Restore exact checkpoint 65ac90e5 in new child ec1765e2. Single draft PR #43 targets main directly. Do not merge stacked PRs out of order. RED 45549703418: 7 failed, 437 passed. Full green CI and manifest verification required before acceptance; no production claims.
