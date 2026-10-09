import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import cli
from src.collector import (
    CollectionError,
    collect_all,
    collect_commits,
    collect_github_metadata,
    get_date_range,
)


def response(output="[]", code=0):
    try:
        items = json.loads(output)
        if isinstance(items, list):
            output = json.dumps(
                {
                    "data": {
                        "scope": {
                            "items": {
                                "nodes": items,
                                "totalCount": len(items),
                                "pageInfo": {"hasNextPage": False, "endCursor": None},
                            }
                        }
                    }
                }
            )
    except ValueError:
        pass
    return subprocess.CompletedProcess(
        ["gh"], code, output, "authentication failed" if code else ""
    )


def repo_record():
    return {
        "name": "example",
        "nameWithOwner": "HemSoft/example",
        "isPrivate": True,
        "description": None,
        "stargazerCount": 0,
        "forkCount": 0,
        "primaryLanguage": None,
    }


class TestCollectionFailures(unittest.TestCase):
    def setUp(self):
        owner_scope = patch.dict(os.environ, REPORT_GITHUB_OWNERS="HemSoft")
        owner_scope.start()
        self.addCleanup(owner_scope.stop)
        self.start, self.end = get_date_range(start_str="2026-09-01", end_str="2026-09-07")

    def test_each_github_source_rejects_failure_timeout_and_invalid_json(self):
        for index, source in enumerate(("enumeration", "pull requests", "issues")):
            for failure in (
                response(code=1),
                subprocess.TimeoutExpired(["gh"], 120),
                response("{broken"),
                response("{}"),
                response('[{"wrong":1}]'),
            ):
                with (
                    self.subTest(source=source, failure=str(failure)),
                    patch(
                        "src.collector.subprocess.run",
                        side_effect=[response(json.dumps([repo_record()])), response()][:index]
                        + [failure],
                    ) as run,
                ):
                    with self.assertRaisesRegex(CollectionError, source):
                        collect_github_metadata(["example"], self.start, self.end)
                    self.assertEqual(run.call_count, index + 1)
                    for call in run.call_args_list:
                        self.assertEqual(call.kwargs["timeout"], 120)

    def test_git_errors_are_visible_including_malformed_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "broken-repo"
            (repo / ".git").mkdir(parents=True)
            for failure in (
                subprocess.CalledProcessError(128, ["git"]),
                subprocess.TimeoutExpired(["git"], 120),
                response("COMMIT_META\tmissing-fields"),
            ):
                with (
                    self.subTest(failure=str(failure)),
                    patch("src.collector.subprocess.run", side_effect=[failure]),
                ):
                    with self.assertRaisesRegex(CollectionError, "Git history.*broken-repo"):
                        collect_commits(directory, self.start, self.end)

    def test_failed_refresh_preserves_valid_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "cache.json"
            with patch("src.collector.subprocess.run", return_value=response()):
                valid = collect_all(
                    directory, start_str="2026-09-01", end_str="2026-09-07", cache_file=cache
                )
            self.assertTrue(valid["collection_complete"])
            before = cache.read_bytes()
            with patch("src.collector.subprocess.run", return_value=response(code=1)):
                with self.assertRaises(CollectionError):
                    collect_all(
                        directory,
                        start_str="2026-09-01",
                        end_str="2026-09-07",
                        cache_file=cache,
                        refresh=True,
                    )
            self.assertEqual(cache.read_bytes(), before)
            with patch("src.collector.subprocess.run") as run:
                self.assertEqual(
                    collect_all(
                        directory, start_str="2026-09-01", end_str="2026-09-07", cache_file=cache
                    ),
                    valid,
                )
                run.assert_not_called()

    def test_legacy_cache_cannot_hide_a_source_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "cache.json"
            cache.write_text(
                json.dumps(
                    {
                        "range": {
                            "start_iso": self.start.isoformat(),
                            "end_iso": self.end.isoformat(),
                        }
                    }
                )
            )
            before = cache.read_bytes()
            with patch("src.collector.subprocess.run", return_value=response(code=1)):
                with self.assertRaises(CollectionError):
                    collect_all(
                        directory, start_str="2026-09-01", end_str="2026-09-07", cache_file=cache
                    )
            self.assertEqual(cache.read_bytes(), before)

    def test_cli_collection_failure_preserves_report_and_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            report, metrics = Path(directory) / "report.html", Path(directory) / "metrics.json"
            report.write_text("last valid report")
            metrics.write_text("last valid metrics")
            args = [
                "cli.py",
                "--base-dir",
                directory,
                "--refresh",
                "--output",
                str(report),
                "--json-out",
                str(metrics),
            ]
            with (
                patch("sys.argv", args),
                patch("src.generator.__file__", str(Path(directory) / "src" / "generator.py")),
                patch("src.collector.subprocess.run", return_value=response(code=1)),
                contextlib.redirect_stderr(io.StringIO()) as stderr,
            ):
                with self.assertRaises(SystemExit) as error:
                    cli.main()
                self.assertEqual(error.exception.code, 1)
                self.assertIn("GitHub repository enumeration", stderr.getvalue())
                self.assertIn("authentication failed", stderr.getvalue())
            self.assertEqual(report.read_text(), "last valid report")
            self.assertEqual(metrics.read_text(), "last valid metrics")
            self.assertEqual(list((Path(directory) / "data").iterdir()), [])

    def test_missing_base_directory_is_a_collection_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(CollectionError, "Repository enumeration"):
                collect_commits(Path(directory) / "missing", self.start, self.end)

    def test_failed_cache_replacement_preserves_prior_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "cache.json"
            cache.write_text("previous valid cache")
            with (
                patch("src.collector.subprocess.run", return_value=response()),
                patch("src.collector.os.replace", side_effect=OSError("disk unavailable")),
            ):
                with self.assertRaisesRegex(OSError, "disk unavailable"):
                    collect_all(directory, cache_file=cache, refresh=True)
            self.assertEqual(cache.read_text(), "previous valid cache")
            self.assertEqual(list(Path(directory).iterdir()), [cache])

    def test_requested_record_fields_are_validated_before_collection_completes(self):
        records = [
            repo_record(),
            {
                "number": 1,
                "title": "Example PR",
                "state": "OPEN",
                "url": "https://github.com/HemSoft/example/pull/1",
                "createdAt": "2026-09-01T12:00:00Z",
                "closedAt": None,
                "mergedAt": None,
            },
            {
                "number": 2,
                "title": "Example issue",
                "state": "OPEN",
                "url": "https://github.com/HemSoft/example/issues/2",
                "createdAt": "2026-09-01T12:00:00Z",
                "closedAt": None,
            },
        ]
        good = [response(json.dumps([record])) for record in records]
        with patch("src.collector.subprocess.run", side_effect=good):
            meta, prs, issues = collect_github_metadata(["example"], self.start, self.end)
        self.assertEqual(len(meta), 1)
        self.assertEqual(len(prs["example"]), 1)
        self.assertEqual(len(issues["example"]), 1)
        for index, record in enumerate(records):
            for field, original in record.items():
                invalid_values = [[], None] if original is not None else [[]]
                for replacement in ["missing", *invalid_values]:
                    invalid = record.copy()
                    if replacement == "missing":
                        del invalid[field]
                    else:
                        invalid[field] = replacement
                    responses = good[:index] + [response(json.dumps([invalid]))]
                    with (
                        self.subTest(source=index, field=field, value=replacement),
                        patch("src.collector.subprocess.run", side_effect=responses),
                    ):
                        with self.assertRaisesRegex(CollectionError, field):
                            collect_github_metadata(["example"], self.start, self.end)
        for field, value in (
            ("state", "UNKNOWN"),
            ("createdAt", "bad-date"),
            ("createdAt", "2026-09-01T12:00:00"),
            ("number", True),
            ("number", -1),
            ("state", "MERGED"),
        ):
            invalid = dict(records[1], **{field: value})
            with (
                self.subTest(field=field, value=value),
                patch(
                    "src.collector.subprocess.run",
                    side_effect=[good[0], response(json.dumps([invalid]))],
                ),
            ):
                with self.assertRaises(CollectionError):
                    collect_github_metadata(["example"], self.start, self.end)
