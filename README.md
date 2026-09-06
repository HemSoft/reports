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

Date ranges include both endpoints in `America/New_York`. Relative windows
look back the requested number of weeks through today, inclusively. Weekly
charts include a final partial bucket when needed. Custom dates must be supplied
together, with the start on or before the end; `--weeks` must be positive.

### Force refresh (bypass cache)

```powershell
python cli.py --weeks 12 --refresh
```

Collection must succeed for every requested source. Git or GitHub failures,
malformed responses, and timeouts stop the CLI with exit 1 and identify the
source; no partial-report mode is enabled. Each Python command has a 120-second
timeout with no automatic retries. Pages uses Bash fail-fast and pipeline error
handling, bounds cloning commands, and stops before artifact upload on failure.
A refresh keeps the previous cache until complete data can replace it atomically;
collection failures leave existing report and metrics files untouched. Older
caches without a completeness marker are recollected once.

### Export raw metrics JSON

```powershell
python cli.py --weeks 12 --json-out "data/audit-q3-metrics.json"
```

## Publishing to GitHub Pages

The report publishes as a single page at the site root (`index.html`).
A scheduled workflow (`.github/workflows/pages.yml`) rebuilds it every
Monday at 08:00 EDT / 07:00 EST and deploys via Actions artifact. Manual runs are
available from the Actions tab.

### One-time setup

1. Create a fine-grained PAT with read access to Contents, Issues, and
   Pull requests on HemSoft repositories
   and save it as the `REPORTS_PAT` repo secret. The workflow stops if this
   secret is missing or a repository cannot be cloned.
2. Enable Pages: repo Settings -> Pages -> Build and deployment ->
   Source: GitHub Actions.
3. Run the workflow once via Actions -> Publish report to GitHub Pages ->
   Run workflow, then open the Pages URL.

Repository discovery follows every GitHub GraphQL cursor for repositories owned
by HemSoft and accessible to the authenticated account. PR and issue histories
are paginated in full, then filtered by creation, closure, or merge events in the
selected interval. Activity without commits still appears in metrics and profiles.
Duplicate records, changing totals, GraphQL errors, missing pages, or stalled
cursors stop collection. A token cannot reveal repositories it cannot access;
use credentials covering the intended repository set. Large histories require
more API requests, and rate-limit failures remain explicit.

The workflow clones all discovered HemSoft repos into `checkouts/`, runs
`python cli.py --weeks 12 --base-dir ./checkouts --output ./public/index.html`,
and uploads `public/` as the Pages artifact. Both `public/` and
`checkouts/` are gitignored build outputs.

The repository remains private, but the Pages site and its exported metrics
are public. Private repository visibility does not restrict access to the site.

## Running tests

```powershell
python -m unittest discover tests
```

## Requirements

- Python 3.10+ (Standard Library only, zero external pip packages needed).
- GitHub CLI (`gh`) authenticated with repository access.
- Local repository clones in `D:\github\HemSoft` (automatically cross-referenced with GitHub remote metadata).
