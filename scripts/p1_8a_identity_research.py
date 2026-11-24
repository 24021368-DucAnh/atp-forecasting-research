"""Run P1.8a against exact original and revised source bytes; aggregate only."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile

from atp_gate.tml_identity_audit import audit_tml_identity
from atp_gate.tml_snapshot import update_tml_season
from scripts.reproduce_pinned_tml_elo import PINS, verified_blob
from scripts.p1_7c_level_a_research import SHA256, NEW_SHA


def main():
    with tempfile.TemporaryDirectory(prefix="tml-identity-") as root:
        root = Path(root)
        paths = []
        for year, pin in sorted(PINS.items()):
            data = verified_blob(pin)
            digest = hashlib.sha256(data).hexdigest()
            if digest != SHA256[year]:
                raise ValueError("original SHA mismatch")
            path = root / f"{year}-{digest}.csv"
            path.write_bytes(data)
            paths.append(path)
        original = audit_tml_identity(paths, expected_sha256=SHA256)
        print(json.dumps({"variant": "ORIGINAL_PINNED", "audit": original},
                         sort_keys=True), flush=True)
        receipt = update_tml_season(2025, root, at=datetime.now(timezone.utc))
        revised = Path(receipt["local_snapshot"])
        report = audit_tml_identity(paths[:4] + [revised],
                                    expected_sha256={**SHA256, 2025: NEW_SHA})
        print(json.dumps({"variant": "REVISED_2025_PINNED", "audit": report},
                         sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
