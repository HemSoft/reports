"""Generate the browser fixture from synthetic data without GitHub or caches."""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))


def main():
    from report_fixture import load_report_fixture
    from src.analyzer import analyze_data
    from src.template import build_html_report

    output = ROOT / "test-results"
    output.mkdir(exist_ok=True)
    analysis = analyze_data(load_report_fixture())
    (output / "report.html").write_text(build_html_report(analysis), encoding="utf-8")
    (output / "metrics.json").write_text(json.dumps(analysis, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
