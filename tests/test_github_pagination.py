import json
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from src.collector import (
    CollectionError,
    collect_all,
    collect_github_metadata,
    get_date_range,
    list_github_repositories,
)
from src.analyzer import analyze_data
from src.template import build_html_report


def repository(name):
    return dict(
        name=name,
        nameWithOwner=f"HemSoft/{name}",
        isPrivate=True,
        description=None,
        stargazerCount=0,
        forkCount=0,
        primaryLanguage=None,
    )


def activity(number, pr=False):
    item = dict(
        number=number,
        title=f"Activity {number}",
        state="CLOSED",
        createdAt="2020-01-01T00:00:00Z",
        closedAt="2026-09-02T12:00:00Z",
        url=f"https://github.com/HemSoft/r100/issues/{number}",
    )
    if pr:
        item.update(state="MERGED", mergedAt=item["closedAt"])
    return item


def page(nodes, total=None, cursor=None, has_next=False):
    body = {
        "data": {
            "scope": {
                "items": {
                    "nodes": nodes,
                    "totalCount": len(nodes) if total is None else total,
                    "pageInfo": {"hasNextPage": has_next, "endCursor": cursor},
                }
            }
        }
    }
    return subprocess.CompletedProcess(["gh"], 0, json.dumps(body), "")


class TestGithubPagination(unittest.TestCase):
    def setUp(self):
        owner_scope = patch.dict(os.environ, REPORT_GITHUB_OWNERS="HemSoft")
        owner_scope.start()
        self.addCleanup(owner_scope.stop)
        self.start, self.end = get_date_range(start_str="2026-09-01", end_str="2026-09-07")

    def test_more_than_100_repositories_and_500_old_events_are_retained(self):
        repos = [repository(f"r{i:03}") for i in range(101)]
        requested = []

        def run(cmd, **kwargs):
            values = dict(value.split("=", 1) for value in cmd if "=" in value)
            self.assertEqual(values["owner"], "HemSoft")
            offset = int(values.get("cursor", "0"))
            query = values["query"]
            if "repositoryOwner" in query:
                items = repos
            else:
                requested.append(values["name"])
                items = (
                    [activity(i + 1, pr="pullRequests" in query) for i in range(501)]
                    if values["name"] == "r100"
                    else []
                )
            next_offset = offset + 100
            return page(
                items[offset:next_offset], len(items), str(next_offset), next_offset < len(items)
            )

        with patch("src.collector.subprocess.run", side_effect=run):
            meta, prs, issues = collect_github_metadata([], self.start, self.end)
        self.assertEqual(len(meta), 101)
        self.assertEqual(set(requested), {repo["name"] for repo in repos})
        self.assertEqual(len(prs["r100"]), 501)
        self.assertEqual(len(issues["r100"]), 501)
        self.assertEqual(prs["r100"][-1]["number"], 501)
        self.assertEqual(issues["r100"][-1]["number"], 501)

    def test_activity_without_commits_reaches_metrics_profiles_and_html(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch(
                "src.collector.subprocess.run",
                side_effect=[
                    page([repository("r100")]),
                    page([activity(1, pr=True)]),
                    page([activity(2)]),
                ],
            ),
        ):
            raw = collect_all(directory, start_str="2026-09-01", end_str="2026-09-07")
        analysis = analyze_data(raw)
        self.assertEqual(analysis["kpis"]["total_commits"], 0)
        self.assertEqual(analysis["kpis"]["merged_prs"], 1)
        self.assertEqual(analysis["kpis"]["closed_issues"], 1)
        self.assertEqual(analysis["kpis"]["active_repos_count"], 1)
        profile = analysis["repo_profiles"][0]
        self.assertEqual(profile["name"], "r100")
        self.assertEqual(profile["commits_share"], 0)
        self.assertIsNone(profile["first_commit"])
        self.assertEqual(profile["primary_language"], "Unknown")
        self.assertIn("r100", build_html_report(analysis))

    def test_incomplete_or_stalled_enumeration_is_rejected(self):
        one, two = repository("one"), repository("two")
        cases = [
            [page([one], total=2)],
            [page([one], total=2, has_next=True)],
            [
                page([one], total=3, cursor="same", has_next=True),
                page([two], total=3, cursor="same", has_next=True),
            ],
            [page([one], total=2, cursor="next", has_next=True), page([one], total=2)],
            [page([one], total=2, cursor="next", has_next=True), page([two], total=3)],
            [page([], total=2, cursor="next", has_next=True)],
            [
                subprocess.CompletedProcess(
                    ["gh"], 0, '{"data":null,"errors":[{"message":"rate limit"}]}', ""
                )
            ],
            [subprocess.CompletedProcess(["gh"], 0, '{"data":{"scope":null}}', "")],
            [page([dict(one, nameWithOwner="Other/one")])],
        ]
        for responses in cases:
            with (
                self.subTest(responses=responses),
                patch("src.collector.subprocess.run", side_effect=responses),
            ):
                with self.assertRaises(CollectionError):
                    list_github_repositories()
