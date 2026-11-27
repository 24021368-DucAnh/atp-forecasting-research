import subprocess
import sys
from pathlib import Path
import time

from atp_lab.worker.lease import read_lease


def _start_worker(data_dir: Path) -> subprocess.Popen:
    program = (
        "from pathlib import Path; import sys, time; "
        "from atp_lab.worker.lease import worker_lease; "
        "lease = worker_lease(Path(sys.argv[1]), worker_id='SYN-worker-test'); "
        "lease.__enter__(); print('READY', flush=True); time.sleep(60)"
    )
    return subprocess.Popen(
        [sys.executable, "-c", program, str(data_dir)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def test_worker_lease_is_exclusive_and_kernel_releases_after_process_exit(tmp_path):
    first = _start_worker(tmp_path)
    try:
        assert first.stdout.readline().strip() == "READY"
        active = read_lease(tmp_path)
        assert active.state == "ACTIVE"
        assert active.worker_id == "SYN-worker-test"
    finally:
        first.terminate()
        first.wait(timeout=10)

    deadline = time.monotonic() + 2.0
    recovered = read_lease(tmp_path)
    while recovered.state == "ACTIVE" and time.monotonic() < deadline:
        time.sleep(0.05)
        recovered = read_lease(tmp_path)
    assert recovered.state == "IDLE"
    assert recovered.worker_id == "SYN-worker-test"


def test_worker_lease_status_does_not_create_files(tmp_path):
    assert read_lease(tmp_path).state == "IDLE"
    assert list(tmp_path.iterdir()) == []
