"""Summarize variance and retained growth from a saved browser measurement."""

import json
import statistics
import sys
from pathlib import Path


def spread(values):
    average = statistics.mean(values)
    cv = statistics.pstdev(values) / average * 100 if average else 0
    return f"{min(values):.1f}/{statistics.median(values):.1f}/{max(values):.1f} ({cv:.1f}%)"


def main():
    path = Path(sys.argv[1])
    report = json.loads(path.read_text(encoding="utf-8"))
    lines = [
        "# Browser benchmark measurements",
        "",
        f"Revision `{report['revision']}`; dirty={report['dirty']}; mode={report['mode']}.",
        f"Environment: {report['environment']['platform']}, Chromium {report['environment']['browser']}, SwiftShader.",
        "",
        "Timing columns show min/median/max and coefficient of variation across repeated samples.",
        "Growth is the maximum post-warm-up delta, not a leak diagnosis. MB uses decimal bytes.",
        "",
        "| Case | Ready ms (CV) | Frame p95 ms (CV) | Main-thread ms/s median | Heap growth MB | RSS growth MB | RSS max MB |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for case in report["cases"]:
        samples = case["samples"]
        heap_growth, rss_growth, rss = [], [], []
        for sample in samples:
            baseline_rss = sum(p["rssBytes"] for p in sample["baseline"]["processes"])
            rss.append(baseline_rss / 1e6)
            for point in sample["retained"]:
                current_rss = sum(p["rssBytes"] for p in point["processes"])
                heap_growth.append((point["heapBytes"] - sample["baseline"]["heapBytes"]) / 1e6)
                rss_growth.append((current_rss - baseline_rss) / 1e6)
                rss.append(current_rss / 1e6)
        lines.append(
            f"| {case['id']} | {spread([s['readyMs'] for s in samples])} | "
            f"{spread([s['frameP95Ms'] for s in samples])} | "
            f"{statistics.median(s['taskMsPerSecond'] for s in samples):.1f} | "
            f"{max(heap_growth):.2f} | {max(rss_growth):.1f} | {max(rss):.1f} |"
        )
    path.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
