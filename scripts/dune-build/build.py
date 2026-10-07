"""Rebuild the checked-in standalone Dune build editor from its source and snapshot."""

import json
from pathlib import Path

SOURCE = Path(__file__).resolve().parent
EDITION = SOURCE.parents[1] / "editions/dune-awakening-build-editor/2026-10-06"


def render():
    data = json.loads((EDITION / "payload.json").read_text(encoding="utf-8"))
    replacements = {
        "__STYLE__": (SOURCE / "style.css").read_text(encoding="utf-8"),
        "__MODEL__": (SOURCE / "model.js").read_text(encoding="utf-8"),
        "__EDITOR__": (SOURCE / "editor.js").read_text(encoding="utf-8"),
        "__DATA__": json.dumps(data, separators=(",", ":")).replace("<", "\\u003c"),
    }
    page = (SOURCE / "page.html").read_text(encoding="utf-8")
    for token, value in replacements.items():
        page = page.replace(token, value)
    return page


if __name__ == "__main__":
    output = EDITION / "report.html"
    output.write_text(render(), encoding="utf-8")
    print(output)
