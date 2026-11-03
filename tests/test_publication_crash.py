"""Crash/restart checks against a separate durable SQLite database."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from tests.source_csv_fixtures import DATA_DIR

WORKER = Path(__file__).with_name("publication_crash_worker.py")


class PublicationCrashTests(SimpleTestCase):
    def test_before_and_after_activation_commit_survive_fresh_process(self):
        cases = (("before_activation", 71, None), ("during_activation", 73, None), ("after_commit", 72, "After restart"))
        for phase, exit_code, expected_name in cases:
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as root:
                self._assert_restarted_state(Path(root), phase, exit_code, expected_name)

    def _assert_restarted_state(self, root, phase, exit_code, expected_name):
        state = self._crash_and_inspect(root, phase, exit_code)
        active = next(version for version, enabled in state["snapshots"] if enabled)
        self.assertEqual(state["name"], expected_name)
        self.assertEqual(active in state["published"], expected_name is not None)
        self.assertEqual(state["active_count"], 1)
        self.assertTrue(state["all_bundles_valid"])
        self.assertEqual(state["policy_version"], active)
        self.assertTrue(state["has_inactive_snapshot"])
        self.assertEqual(state["product_prices_valid"], expected_name is not None)

    def _crash_and_inspect(self, root, phase, exit_code):
        source = root / "data"
        shutil.copytree(DATA_DIR, source)
        environment = {
            **os.environ,
            "EMPORIO_DB_PATH": str(root / "db.sqlite3"),
            "EMPORIO_BUNDLE_ROOT": str(root / "bundles"),
            "PYTHONPATH": str(WORKER.parents[1]),
        }
        command = [sys.executable, str(WORKER), "publish", str(source), str(root / "bundles"), phase]
        crashed = subprocess.run(command, env=environment, check=False, capture_output=True)
        self.assertEqual(crashed.returncode, exit_code, crashed.stderr.decode(errors="replace"))
        fresh = subprocess.run(
            [sys.executable, str(WORKER), "inspect"], env=environment,
            check=True, capture_output=True,
        )
        return json.loads(fresh.stdout)
