#!/usr/bin/env python3
"""Verify original tracked files against the frozen Git tree, not handover metadata."""
import hashlib
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parent.parent
manifest = json.loads((root / "handover/08_ORIGINAL_TREE.json").read_text(encoding="utf-8"))
entries = manifest["files"]
if len(entries) != manifest["file_count"] or len({x["path"] for x in entries}) != len(entries):
    raise SystemExit("invalid inventory")
errors = []
sha256 = []
for entry in entries:
    rel = Path(entry["path"])
    if rel.is_absolute() or ".." in rel.parts:
        raise SystemExit("invalid path in inventory")
    p = root / rel
    if p.is_symlink() or not p.is_file():
        errors.append(f"missing/nonregular: {rel}")
        continue
    data = p.read_bytes()
    blob = hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()
    if len(data) != entry["size"] or blob != entry["git_blob_sha1"]:
        errors.append(f"size/hash mismatch: {rel}")
        continue
    sha256.append(f"{hashlib.sha256(data).hexdigest()}  {entry['path']}")
if errors:
    print("\n".join(errors), file=sys.stderr)
    raise SystemExit(1)
out = root / "handover/VERIFIED_SHA256_LOCAL.txt"
out.write_text("\n".join(sha256) + "\n", encoding="utf-8")
print(f"PASS: {len(sha256)} original blobs verified; local SHA256 list: {out}")
