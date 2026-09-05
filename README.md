# HemSoft productivity audit tool

Automated audit reporting engine for engineering throughput, pull request velocity, code churn, and temporal cadence across `github.com/HemSoft` repositories.

The tool generates standalone interactive HTML dashboards with Three.js 3D bar models and Chart.js analytics.

## Output

- Primary report location: `D:\hemsoft-productivity.html`
- Standalone HTML with embedded CSS and WebGL renderers.
- No local server required. Open directly in any modern browser.

## Features

- **3D weekly velocity bars**: WebGL volumetric rendering of commits, merged PRs, and code churn over time. Includes orbit controls, specular lighting, and hover raycasting tooltips.
- **3D day and hour matrix**: 7x24 extruded bar landscape displaying coding cadence across all 168 hours of the week in Eastern Time (`America/New_York`).
- **Comprehensive KPIs**: Total commits, net lines of code (+added / -deleted), unique files touched, PR merge rate, median turnaround time, issue resolution rate, active days ratio, longest streak, and diurnal distribution.
- **Repository deep dive**: Full breakdown across all active repositories with commits, pull requests, issues, and language stats.
- **Auditing filters**: Searchable and filterable tables for repositories, recent pull requests, and commit logs with links directly to GitHub.
- **Arbitrary timeframes**: Audit any historical period using `--weeks <N>` or explicit `--start YYYY-MM-DD` and `--end YYYY-MM-DD` dates.

## Architecture

```
reports/
├── cli.py               # Main CLI entry point
├── src/
│   ├── collector.py     # Git numstats, worktree deduplication, and GitHub API queries
│   ├── analyzer.py      # KPI aggregation, 7x24 matrices, and PR cycle times
│   ├── template.py      # Standalone HTML dashboard generator with 3D/2D visualizers
│   └── generator.py     # End-to-end orchestration and cache management
├── tests/               # Automated unit and integration test suite
│   ├── test_collector.py
│   ├── test_analyzer.py
│   └── test_generator.py
├── data/                # Local cache storage (cache_12w.json)
└── package.json         # Optional npm convenience scripts
```

## Quick start

### Generate default 12-week report

```powershell
python cli.py --weeks 12 --output "D:\hemsoft-productivity.html"
```

### Custom date range

```powershell
python cli.py --start 2026-06-01 --end 2026-09-01 --output "D:\audit-q3.html"
```

### Force refresh (bypass cache)

```powershell
python cli.py --weeks 12 --refresh
```

### Export raw metrics JSON

```powershell
python cli.py --weeks 12 --json-out "data/audit-q3-metrics.json"
```

## Running tests

```powershell
python -m unittest discover tests
```

## Requirements

- Python 3.10+ (Standard Library only, zero external pip packages needed).
- GitHub CLI (`gh`) authenticated with repository access.
- Local repository clones in `D:\github\HemSoft` (automatically cross-referenced with GitHub remote metadata).
