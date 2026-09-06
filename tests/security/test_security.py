"""Integration probes run by the security job with its scanner dependencies."""

import base64
import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import check_security


class SecurityChecks(unittest.TestCase):
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
