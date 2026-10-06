"""Embed the verified committed graphics bundle without a Node runtime dependency."""

import base64
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def graphics_script():
    manifest = json.loads((ROOT / "assets/report-graphics.json").read_text(encoding="utf-8"))
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    if (
        manifest["schema"] != 1
        or manifest["versions"]["three"] != package["devDependencies"]["three"]
    ):
        raise ValueError("Graphics bundle version differs from declared Three.js dependency")
    data = (ROOT / "assets/report-graphics.js").read_bytes()
    integrity = "sha384-" + base64.b64encode(hashlib.sha384(data).digest()).decode()
    if len(data) != manifest["bytes"] or integrity != manifest["integrity"]:
        raise ValueError("Graphics bundle bytes differ from integrity manifest")
    source = "data:application/javascript;base64," + base64.b64encode(data).decode()
    return (
        f'<script src="{source}#report-graphics.js" integrity="{integrity}" '
        'crossorigin="anonymous"></script>'
    )
