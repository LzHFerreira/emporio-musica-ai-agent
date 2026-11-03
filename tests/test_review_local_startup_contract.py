import os
import socket
import subprocess
import sys
import tempfile
import time

import httpx
from pathlib import Path

from django.conf import settings


ROOT = Path(__file__).resolve().parents[1]


def test_development_hosts_are_explicit_and_loopback_only():
    hosts = set(settings.ALLOWED_HOSTS)
    assert {"localhost", "127.0.0.1", "[::1]"} <= hosts
    assert "*" not in hosts


def _port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _environment(database):
    return {
        **os.environ,
        "EMPORIO_DB_PATH": database,
        "META_WEBHOOK_VERIFY_TOKEN": "review-verify",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def _start(port, env):
    return subprocess.Popen(
        [sys.executable, str(ROOT / "manage.py"), "runserver", f"127.0.0.1:{port}", "--noreload"],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def _assert_webhook_ready(process, url):
    for _ in range(40):
        if process.poll() is not None:
            raise AssertionError("runserver exited before accepting requests")
        try:
            response = httpx.get(url, timeout=0.25)
            assert (response.status_code, response.content) == (200, b"ready")
            return
        except (httpx.ConnectError, httpx.TimeoutException):
            time.sleep(0.1)
    raise AssertionError("runserver did not accept loopback request")


def _stop(process):
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def test_runserver_accepts_local_webhook_verification():
    with tempfile.TemporaryDirectory() as directory:
        port = _port()
        url = f"http://127.0.0.1:{port}/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=review-verify&hub.challenge=ready"
        process = _start(port, _environment(os.path.join(directory, "review.sqlite3")))
        try:
            _assert_webhook_ready(process, url)
        finally:
            _stop(process)
