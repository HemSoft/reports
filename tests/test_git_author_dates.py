import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from src.collector import collect_commits, get_date_range


class TestGitAuthorDates(unittest.TestCase):
    def test_real_git_author_interval_is_independent_of_committer_dates_and_host_zone(self):
        start, end = get_date_range(start_str="2026-09-01", end_str="2026-09-07")
        cases = [
            ("included-rebased", "2026-09-02T12:00:00-04:00", "2026-09-08T12:00:00-04:00"),
            ("excluded-imported", "2026-08-31T12:00:00-04:00", "2026-09-02T12:00:00-04:00"),
            ("included-start", "2026-09-01T04:00:00Z", "2026-08-20T12:00:00Z"),
            ("included-end", "2026-09-08T03:59:59Z", "2026-09-20T12:00:00Z"),
            ("excluded-before", "2026-09-01T03:59:59Z", "2026-09-02T12:00:00Z"),
            ("excluded-after", "2026-09-08T04:00:00Z", "2026-09-02T12:00:00Z"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "fixture"
            subprocess.run(["git", "init", "--quiet", str(repo)], check=True, timeout=30)
            for subject, authored, committed in cases:
                env = dict(os.environ, GIT_AUTHOR_DATE=authored, GIT_COMMITTER_DATE=committed)
                subprocess.run(["git", "-C", str(repo), "-c", "user.name=Fixture",
                                "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false",
                                "-c", "core.hooksPath=/dev/null", "commit", "--quiet", "--allow-empty", "-m", subject],
                               env=env, check=True, timeout=30)
            results = []
            for host_zone in ("UTC", "America/New_York"):
                with self.subTest(host_zone=host_zone), patch.dict(os.environ, {"TZ": host_zone}):
                    commits = collect_commits(directory, start, end)
                    results.append([(c["hash"], c["author_date"], c["timestamp"]) for c in commits])
                    self.assertEqual({c["subject"] for c in commits},
                                     {"included-rebased", "included-start", "included-end"})
                    self.assertEqual(len(commits), 3)
            self.assertEqual(results[0], results[1])
