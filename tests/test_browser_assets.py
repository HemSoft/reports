import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import browser_assets


class BrowserAssetsTests(unittest.TestCase):
    def test_embedded_bytes_and_integrity_match_committed_bundle(self):
        script = browser_assets.graphics_script()
        encoded = script.split("base64,", 1)[1].split("#", 1)[0]
        data = base64.b64decode(encoded, validate=True)
        self.assertEqual(data, (browser_assets.ROOT / "assets/report-graphics.js").read_bytes())
        digest = base64.b64encode(hashlib.sha384(data).digest()).decode()
        self.assertIn(f'integrity="sha384-{digest}"', script)
        self.assertIn('crossorigin="anonymous"', script)

    def test_corrupted_bytes_size_and_version_fail_before_rendering(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "assets").mkdir()
            data = b"window.syntheticGraphics = true;"
            manifest = {
                "schema": 1,
                "versions": {"three": "0.186.1"},
                "bytes": len(data),
                "integrity": "sha384-" + base64.b64encode(hashlib.sha384(data).digest()).decode(),
            }
            (root / "package.json").write_text(
                json.dumps({"devDependencies": {"three": "0.186.1"}}), encoding="utf-8"
            )
            asset = root / "assets/report-graphics.js"
            metadata = root / "assets/report-graphics.json"
            asset.write_bytes(data)
            metadata.write_text(json.dumps(manifest), encoding="utf-8")
            with patch.object(browser_assets, "ROOT", root):
                self.assertIn("report-graphics.js", browser_assets.graphics_script())
                asset.write_bytes(data.replace(b"true", b"evil"))
                with self.assertRaisesRegex(ValueError, "bytes differ"):
                    browser_assets.graphics_script()
                asset.write_bytes(data)
                for field, value in (("bytes", len(data) + 1), ("schema", 2)):
                    altered = dict(manifest, **{field: value})
                    metadata.write_text(json.dumps(altered), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        browser_assets.graphics_script()
                manifest["versions"]["three"] = "0.128.0"
                metadata.write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "version differs"):
                    browser_assets.graphics_script()
