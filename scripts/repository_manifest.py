"""Canonical SHA256 manifest of regular tracked Git index blobs.

No raw data discovery, no ignored/untracked paths, no recursive self-hash.
A clean tracked working tree is required for verification (Git handles CRLF).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess

NAME = "MANIFEST_SHA256.txt"


def _git(root, *args):
    try:
        return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.PIPE)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError("Git repository/index unavailable") from exc


def build_manifest(root: Path) -> str:
    root = Path(root).resolve()
    top = Path(_git(root, "rev-parse", "--show-toplevel").decode("utf-8").strip()).resolve()
    if top != root:
        raise ValueError("manifest root must be repository root")
    entries = {}
    for record in _git(root, "ls-files", "--stage", "-z").split(b"\0"):
        if not record:
            continue
        metadata, path_bytes = record.split(b"\t", 1)
        mode, oid, stage = metadata.decode("ascii").split()
        path = path_bytes.decode("utf-8")
        parts = PurePosixPath(path)
        if (stage != "0" or path in entries or mode not in {"100644","100755"}
                or parts.is_absolute() or ".." in parts.parts
                or any(c in path for c in ("\n","\r","\t","\\"))):
            raise ValueError("unsupported or conflicted tracked file")
        entries[path] = oid
    if NAME not in entries:
        raise ValueError("manifest must itself be tracked")
    lines = []
    for path, oid in sorted(entries.items()):
        if path == NAME:
            continue
        data = _git(root, "cat-file", "blob", oid)
        lines.append(f"{hashlib.sha256(data).hexdigest()}  {path}\n")
    return "".join(lines)


def verify_manifest(root: Path) -> int:
    root = Path(root).resolve()
    expected = build_manifest(root)
    status = subprocess.run(["git","-C",str(root),"diff","--quiet","--",".",
                             f":(exclude){NAME}"],check=False).returncode
    if status != 0:
        raise ValueError("dirty or changed tracked working tree")
    try:
        actual = (root / NAME).read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError("manifest unreadable") from exc
    if actual != expected:
        raise ValueError("manifest SHA256 or tracked coverage mismatch")
    return len(expected.splitlines())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode",choices=("generate","verify","emit-json"))
    parser.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    try:
        if args.mode == "verify":
            print(f"PASS: {verify_manifest(args.root)} tracked files match SHA256")
        elif args.mode == "generate":
            data = build_manifest(args.root)
            (args.root / NAME).write_bytes(data.encode("utf-8"))
            print(f"Generated {len(data.splitlines())} tracked hashes; stage and commit manifest")
        else:
            print("P1_9D_MANIFEST_JSON="+json.dumps(build_manifest(args.root),ensure_ascii=True))
        return 0
    except (ValueError,OSError) as exc:
        print(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
