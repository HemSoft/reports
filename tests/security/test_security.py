"""Integration probes run by the security job with its scanner dependencies."""

import base64
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import check_security


class SecurityChecks(unittest.TestCase):
    def test_embedded_inventory_rejects_modified_bytes_and_missing_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "assets").mkdir()
            data = b"synthetic bundled graphics"
            (root / "assets/report-graphics.js").write_bytes(data)
            digest = base64.b64encode(hashlib.sha384(data).digest()).decode()
            encoded = base64.b64encode(data).decode()
            markup = (
                f'<script src="data:application/javascript;base64,{encoded}#report-graphics.js" '
                f'integrity="sha384-{digest}" crossorigin="anonymous"></script>'
            )
            with (
                patch.object(check_security, "ROOT", root),
                patch.object(check_security, "SCRIPT_FILES", {}),
            ):
                self.assertRegex(digest, check_security.verified_digest_pattern(markup))
                modified = markup.replace(encoded, base64.b64encode(data + b"modified").decode())
                with self.assertRaisesRegex(ValueError, "bytes differ"):
                    check_security.verified_digest_pattern(modified)
                with self.assertRaisesRegex(ValueError, "inventory differs"):
                    check_security.verified_digest_pattern("")

    def test_browser_url_version_must_match_dependency_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            versions = {"chart.js": "4.5.1", "three": "0.128.0"}
            (root / "package.json").write_text(json.dumps({"devDependencies": versions}))
            (root / "package-lock.json").write_text(
                json.dumps(
                    {
                        "packages": {
                            f"node_modules/{name}": {"version": value}
                            for name, value in versions.items()
                        }
                    }
                )
            )
            for name, value in versions.items():
                folder = root / "node_modules" / name
                folder.mkdir(parents=True)
                (folder / "package.json").write_text(json.dumps({"version": value}))
            old = "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.js"
            current = old.replace("4.4.1", "4.5.1")
            with patch.object(check_security, "ROOT", root):
                with patch.object(check_security, "SCRIPT_FILES", {old: "unused"}):
                    with self.assertRaisesRegex(ValueError, "Browser URL version"):
                        check_security.check_browser_versions()
                with patch.object(check_security, "SCRIPT_FILES", {current: "unused"}):
                    check_security.check_browser_versions()
                    (root / "node_modules/chart.js/package.json").write_text(
                        json.dumps({"version": "4.4.1"})
                    )
                    with self.assertRaisesRegex(ValueError, "metadata versions"):
                        check_security.check_browser_versions()

    def test_local_composite_action_references_are_checked_recursively(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workflows = root / ".github/workflows"
            workflows.mkdir(parents=True)
            (workflows / "probe.yml").write_text(
                "permissions: {contents: read}\njobs: {test: {steps: [{uses: './local/outer'}]}}",
                encoding="utf-8",
            )
            for name in ("outer", "inner"):
                (root / "local" / name).mkdir(parents=True)
            (root / "local/outer/action.yml").write_text(
                "runs: {using: composite, steps: [{uses: './local/inner'}]}", encoding="utf-8"
            )
            inner = root / "local/inner/action.yaml"
            inner.write_text(
                "runs: {using: composite, steps: [{uses: actions/checkout@v4}]}", encoding="utf-8"
            )
            with patch.object(check_security, "ROOT", root):
                with self.assertRaisesRegex(ValueError, "Mutable action"):
                    check_security.check_policy()
                inner.write_text(
                    "runs: {using: composite, steps: [{uses: 'actions/checkout@"
                    + "a" * 40
                    + "'}]}",
                    encoding="utf-8",
                )
                check_security.check_policy()

    def test_mutable_reference_and_excess_permissions_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workflows = root / ".github/workflows"
            workflows.mkdir(parents=True)
            for text in (
                "permissions: {contents: read}\njobs:\n  test:\n    steps:\n      - uses: actions/checkout@v4\n",
                "permissions: {contents: read}\njobs: {test: {steps: [{uses: actions/checkout@v4}]}}\n",
                "permissions: {contents: read}\njobs: {test: {uses: owner/repo/.github/workflows/reuse.yml@main}}\n",
                "permissions: {contents: write}\njobs:\n  test:\n    steps: []\n",
            ):
                for extension in ("yml", "yaml"):
                    path = workflows / f"probe.{extension}"
                    path.write_text(text, encoding="utf-8")
                    with patch.object(check_security, "ROOT", root):
                        with self.assertRaises(ValueError):
                            check_security.check_policy()
                    path.unlink()

    def test_only_the_pages_archive_job_may_write_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workflows = root / ".github/workflows"
            workflows.mkdir(parents=True)
            cases = (
                ("pages", "archive", "{contents: write}", True),
                ("pages", "build", "{contents: write}", False),
                ("pages", "archive", "{contents: write, pages: write}", False),
                ("other", "archive", "{contents: write}", False),
            )
            for stem, job, permissions, allowed in cases:
                with self.subTest(stem=stem, job=job, permissions=permissions):
                    path = workflows / f"{stem}.yml"
                    path.write_text(
                        f"jobs:\n  {job}:\n    permissions: {permissions}\n    steps: []\n",
                        encoding="utf-8",
                    )
                    with patch.object(check_security, "ROOT", root):
                        if allowed:
                            check_security.check_policy()
                        else:
                            with self.assertRaisesRegex(ValueError, "Unexpected permissions"):
                                check_security.check_policy()
                    path.unlink()

    def test_unicode_file_secret_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
            # Synthetic, unissued token built at runtime, with UTF-8-only text.
            value = "ghp_" + "".join(chr(65 + (index * 7) % 26) for index in range(36))
            (root / "unicode.txt").write_text(
                '\U0001f512\ncredential = "' + value + '"\n', encoding="utf-8"
            )
            subprocess.run(["git", "-C", str(root), "add", "unicode.txt"], check=True)
            with patch.object(check_security, "ROOT", root):
                with self.assertRaisesRegex(ValueError, "Secret scan"):
                    check_security.scan_secrets()

    def test_digest_exception_requires_matching_dependency_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            data = b"synthetic dependency"
            (root / "dependency.js").write_bytes(data)
            digest = base64.b64encode(hashlib.sha384(data).digest()).decode()
            (root / "src/template.py").write_text(
                f'<script src="https://fixture.test/lib.js" integrity="sha384-{digest}" crossorigin="anonymous"></script>',
                encoding="utf-8",
            )
            with (
                patch.object(check_security, "ROOT", root),
                patch.object(
                    check_security,
                    "SCRIPT_FILES",
                    {"https://fixture.test/lib.js": "dependency.js"},
                ),
            ):
                pattern = check_security.verified_digest_pattern()
                self.assertRegex(digest, pattern)
                template = root / "src/template.py"
                original = template.read_text(encoding="utf-8")
                template.write_text(
                    original + "<script src='https://fixture.test/extra.js'></script>",
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(ValueError, "lacks SHA-384"):
                    check_security.verified_digest_pattern()
                template.write_text(original, encoding="utf-8")
                (root / "dependency.js").write_bytes(data + b"changed")
                with self.assertRaisesRegex(ValueError, "does not match"):
                    check_security.verified_digest_pattern()
