import json
from pathlib import Path


def load_report_fixture():
    return json.loads(
        (Path(__file__).parent / "fixtures" / "report.json").read_text(encoding="utf-8")
    )
