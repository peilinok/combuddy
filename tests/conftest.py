import threading
import time
import pytest
from combuddy import scan_service, download_service

def _reset_status():
    scan_service.STATUS.update(running=False, phase="idle", models_found=0,
                                bases_done=0, workflows_done=0, errors=0,
                                hash_done=0, hash_total=0,
                                enrich_done=0, enrich_total=0, cancel=False, revision=0)
    download_service.DOWNLOAD_STATUS.update(running=False, phase="idle", filename="",
                                            downloaded=0, total=0, error=None, cancel=False, revision=0)

def _wait_for_scan_to_finish(timeout=5.0, interval=0.01):
    deadline = time.time() + timeout
    while scan_service.STATUS["running"] and time.time() < deadline:
        time.sleep(interval)

@pytest.fixture(autouse=True)
def _isolate_scan_status():
    """Every test gets a clean scan_service.STATUS, and any background scan
    thread spawned by a test (e.g. via POST /api/scan) is drained before the
    next test runs, so leaked threads can't bleed STATUS across tests.

    threading.Thread(...).start() returns before the OS has necessarily
    scheduled the new thread, so it can still be sitting at "not yet started"
    when the test body returns -- STATUS["running"] hasn't flipped True yet
    either. Polling STATUS alone can't tell "not started" apart from
    "already finished", so we first join any thread spawned during the test
    (tracked via threading.enumerate(), which registers a thread the instant
    start() returns) before falling back to the STATUS poll.
    """
    _reset_status()
    before = set(threading.enumerate())
    yield
    leaked = [t for t in threading.enumerate() if t not in before]
    for t in leaked:
        t.join(timeout=5.0)
    _wait_for_scan_to_finish()
    _reset_status()
