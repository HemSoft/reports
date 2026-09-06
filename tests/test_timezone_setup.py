import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


class TestTimezoneSetup(unittest.TestCase):
    def run_python(self, *args):
        return subprocess.run(
            [sys.executable, *args],
            cwd=Path(__file__).resolve().parents[1],
            env=dict(os.environ, PYTHONTZPATH=""),
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )

    def test_cli_help_with_packaged_timezone_data(self):
        result = self.run_python("cli.py", "--help")
        self.assertIn("--weeks", result.stdout)
        self.assertIn("--base-dir", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_packaged_eastern_winter_and_summer_offsets(self):
        result = self.run_python(
            "-c",
            "import json; from datetime import datetime; from zoneinfo import ZoneInfo; "
            "z=ZoneInfo('America/New_York'); "
            "print(json.dumps([datetime(2026,m,15,tzinfo=z).utcoffset().total_seconds()/3600 for m in (1,7)]))",
        )
        self.assertEqual(json.loads(result.stdout), [-5, -4])
