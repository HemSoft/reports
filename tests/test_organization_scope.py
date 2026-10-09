"""Collection and rendering retain canonical identity across an owner transfer."""

import copy
import os
import unittest
from unittest.mock import patch

from report_fixture import load_report_fixture
from test_github_pagination import page, repository
from src.analyzer import analyze_data
from src.collector import CollectionError, _cache_inputs, get_date_range, list_github_repositories
from src.github_identity import github_owners, repository_identity
from src.template import build_html_report


class OrganizationScopeTests(unittest.TestCase):
    def test_default_scope_keeps_retained_repositories_and_organization(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(github_owners(), ["HemSoft", "hemsoft-dev"])
        self.assertEqual(repository_identity("hs-buddy"), "hemsoft-dev/hs-buddy")
        for name in ("now-leadership-group", "set-it-free-loop-site"):
            self.assertEqual(repository_identity(name), f"HemSoft/{name}")

    def test_owners_are_enumerated_with_independent_pagination(self):
        personal = repository("retained")
        org = [
            dict(repository(name), nameWithOwner=f"hemsoft-dev/{name}") for name in ("one", "two")
        ]
        with (
            patch.dict(os.environ, REPORT_GITHUB_OWNERS="HemSoft,hemsoft-dev"),
            patch(
                "src.collector.subprocess.run",
                side_effect=[
                    page([personal]),
                    page(org[:1], total=2, cursor="next", has_next=True),
                    page(org[1:], total=2),
                ],
            ) as run,
        ):
            result = list_github_repositories()
        self.assertEqual(set(result), {"retained", "one", "two"})
        calls = [dict(v.split("=", 1) for v in c.args[0] if "=" in v) for c in run.call_args_list]
        self.assertEqual([c["owner"] for c in calls], ["HemSoft", "hemsoft-dev", "hemsoft-dev"])
        self.assertNotIn("cursor", calls[1])
        self.assertEqual(calls[2]["cursor"], "next")

    def test_duplicate_basename_or_unexpected_owner_stops_collection(self):
        with patch.dict(os.environ, REPORT_GITHUB_OWNERS="HemSoft,hemsoft-dev"):
            for canonical in ("hemsoft-dev/SAME", "Other/SAME"):
                with (
                    self.subTest(canonical=canonical),
                    patch(
                        "src.collector.subprocess.run",
                        side_effect=[
                            page([repository("same")]),
                            page([dict(repository("SAME"), nameWithOwner=canonical)]),
                        ],
                    ),
                    self.assertRaises(CollectionError),
                ):
                    list_github_repositories()

    def test_invalid_and_duplicate_owner_scope_is_rejected(self):
        for owners in (
            "",
            "HemSoft,",
            "HemSoft,hemsoft",
            "-bad",
            "../HemSoft",
            "HemSoft/org",
            "a" * 40,
        ):
            with self.subTest(owners=owners), patch.dict(os.environ, REPORT_GITHUB_OWNERS=owners):
                with self.assertRaises(ValueError):
                    github_owners()

    def test_owner_scope_changes_cache_identity(self):
        start, end = get_date_range(start_str="2026-09-01", end_str="2026-09-07")
        with patch.dict(os.environ, REPORT_GITHUB_OWNERS="HemSoft"):
            old = _cache_inputs(".", 1, start, end)
        with patch.dict(os.environ, REPORT_GITHUB_OWNERS="HemSoft,hemsoft-dev"):
            new = _cache_inputs(".", 1, start, end)
        self.assertNotEqual(old, new)
        self.assertEqual(new["github_owners"], ["HemSoft", "hemsoft-dev"])

    def test_profiles_and_recent_commits_use_collected_canonical_owner(self):
        raw = load_report_fixture()
        raw["repo_meta"]["hs-buddy"]["nameWithOwner"] = "hemsoft-dev/hs-buddy"
        raw["repo_meta"]["retained"] = dict(
            raw["repo_meta"]["hs-buddy"], nameWithOwner="HemSoft/retained"
        )
        raw["commits"].append(dict(raw["commits"][0], repo="retained", hash="f" * 40))
        original = copy.deepcopy(raw)
        rendered = build_html_report(analyze_data(raw))
        self.assertIn('href="https://github.com/hemsoft-dev/hs-buddy"', rendered)
        self.assertIn('href="https://github.com/hemsoft-dev/hs-buddy/commit/', rendered)
        self.assertNotIn('href="https://github.com/HemSoft/hs-buddy', rendered)
        self.assertTrue('href="https://github.com/HemSoft/retained"' in rendered)
        self.assertEqual(raw, original)

    def test_repository_identity_rejects_injection_and_mismatched_names(self):
        for canonical in (
            'org/name" onclick="x',
            "org/../name",
            "https://evil/name",
            "org/other",
            "org/..",
        ):
            with self.subTest(canonical=canonical), self.assertRaises(ValueError):
                repository_identity("name", canonical)
