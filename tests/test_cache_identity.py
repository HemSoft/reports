import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.collector import cache_source_key, collect_all


class TestCacheIdentity(unittest.TestCase):
    def collect(self, source, cache, **kwargs):
        return collect_all(source, start_str="2026-09-01", end_str="2026-09-07", cache_file=cache, **kwargs)

    def test_source_a_cache_is_never_reused_for_source_b(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory) / "a", Path(directory) / "b"
            a.mkdir()
            b.mkdir()
            cache = Path(directory) / "shared.json"
            with patch("src.collector.collect_commits", return_value=[]), \
                    patch("src.collector.collect_github_metadata", return_value=({"marker": "A"}, {}, {})):
                self.collect(a, cache)
            with patch("src.collector.collect_commits", return_value=[]) as scan, \
                    patch("src.collector.collect_github_metadata", return_value=({"marker": "B"}, {}, {})):
                actual = self.collect(b, cache)
                scan.assert_called_once()
            self.assertEqual(actual["repo_meta"]["marker"], "B")
            self.assertNotEqual(cache_source_key(a), cache_source_key(b))

    def test_equivalent_source_hit_and_forced_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            source.mkdir()
            cache = Path(directory) / "cache.json"
            with patch("src.collector.collect_commits", return_value=[]), \
                    patch("src.collector.collect_github_metadata", return_value=({}, {}, {})):
                expected = self.collect(source, cache)
            alias = source / ".." / "source"
            self.assertEqual(cache_source_key(source), cache_source_key(alias))
            self.assertEqual(cache_source_key(Path.cwd() / "src"), cache_source_key("src"))
            with patch("src.collector.collect_commits", side_effect=AssertionError("unexpected scan")):
                self.assertEqual(self.collect(alias, cache), expected)
            with patch("src.collector.collect_commits", return_value=[]) as scan, \
                    patch("src.collector.collect_github_metadata", return_value=({}, {}, {})):
                self.collect(alias, cache, refresh=True)
                scan.assert_called_once()

    def test_stale_schema_inputs_and_malformed_envelopes_are_recollected(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "cache.json"
            with patch("src.collector.collect_commits", return_value=[]), \
                    patch("src.collector.collect_github_metadata", return_value=({}, {}, {})):
                valid = self.collect(directory, cache)
            variants = [[], {}, dict(valid, cache_schema_version=-1), dict(valid, commits=None)]
            for key in valid["cache_inputs"]:
                altered = copy.deepcopy(valid)
                altered["cache_inputs"][key] = "different"
                variants.append(altered)
            for value in variants:
                cache.write_text(json.dumps(value), encoding="utf-8")
                with self.subTest(value=value), patch("src.collector.collect_commits", return_value=[]) as scan, \
                        patch("src.collector.collect_github_metadata", return_value=({}, {}, {})):
                    actual = self.collect(directory, cache)
                    scan.assert_called_once()
                    self.assertEqual(actual["cache_inputs"], valid["cache_inputs"])
            cache.write_text("{broken", encoding="utf-8")
            with patch("src.collector.collect_commits", return_value=[]) as scan, \
                    patch("src.collector.collect_github_metadata", return_value=({}, {}, {})):
                self.collect(directory, cache)
                scan.assert_called_once()
