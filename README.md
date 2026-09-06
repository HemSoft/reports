# HemSoft productivity audit tool

Automated audit reporting engine for engineering throughput, pull request velocity, code churn, and temporal cadence across `github.com/HemSoft` repositories.

The tool generates standalone interactive HTML dashboards with Three.js 3D bar models and Chart.js analytics.

## Output

- Primary report location: `D:\hemsoft-productivity.html`
- Single HTML file with embedded report data and CSS; chart libraries load from CDNs.
- No local server required. Open directly in any modern browser.

Interactive charts require access to `cdn.jsdelivr.net` (Chart.js and OrbitControls)
and `cdnjs.cloudflare.com` (Three.js). Google Fonts and GitHub avatars are optional
network resources; browser fonts and report text remain usable without them.
3D views also require WebGL. The generated file is not a fully bundled offline app.

If a visualization library is blocked or graphics initialization fails, each affected
view displays an unavailable notice. A failed scene or chart leaves the independent
views running; unavailable 3D controls are disabled. With networking disabled,
embedded metrics, repository/PR/commit tables, tab navigation, and filtering still
work. Outbound GitHub links require connectivity.

## Features

- **3D weekly velocity bars**: WebGL volumetric rendering of commits, merged PRs, and code churn over time. Includes orbit controls, specular lighting, and hover raycasting tooltips.
- **3D day and hour matrix**: 7x24 extruded bar landscape displaying coding cadence across all 168 hours of the week in Eastern Time (`America/New_York`).
- **Comprehensive KPIs**: Total commits, net lines of code (+added / -deleted), unique files touched, PR merge rate, median turnaround time, issue resolution rate, active days ratio, longest streak, and diurnal distribution.
- **Repository deep dive**: Full breakdown across all active repositories with commits, pull requests, issues, and language stats.
- **Auditing filters**: Searchable and filterable tables for repositories, recent pull requests, and commit logs with links directly to GitHub.
- **Arbitrary timeframes**: Audit any historical period using `--weeks <N>` or explicit `--start YYYY-MM-DD` and `--end YYYY-MM-DD` dates.

Repository profile language follows the largest file-churn total in the selected
interval. Without file-derived language, it uses GitHub's primary language.
Missing, null, or empty language metadata displays `Unknown`, including repositories
whose commits change no files.

PR cycle-time medians use merged PRs with a known creation-to-merge duration.
Even-sized samples average the middle two values; odd-sized samples use the
middle value. The result is rounded to two decimal places in hours. With no
known durations, the reported median is `0.0`.

## Architecture

```text
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

Create and activate a virtual environment, then install the pinned runtime dependency.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python cli.py --help
```

Linux:

On Debian/Ubuntu, install the `python3-venv` OS package first if venv reports
that `ensurepip` is unavailable.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python cli.py --help
```

The remaining Python commands assume this environment is active. `tzdata` supplies
IANA timezone data on Windows and serves as a fallback on Linux. Python explains
this dependency in its [zoneinfo data-source documentation](https://docs.python.org/3/library/zoneinfo.html#data-sources).
Update the pin in `requirements.txt` when adopting a new timezone database and
rerun the tests, which check packaged Eastern winter and summer offsets.

If the Linux OS package cannot be installed, bootstrap pip inside the environment
using pip's [supported get-pip method](https://pip.pypa.io/en/stable/installation/#get-pip-py):

```bash
python3 -m venv --without-pip .venv
curl --fail --location --output .venv/get-pip.py https://bootstrap.pypa.io/get-pip.py
.venv/bin/python .venv/get-pip.py
source .venv/bin/activate
python -m pip install -r requirements.txt
python cli.py --help
```

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

Commit cadence and interval membership use Git author dates, converted to
`America/New_York`. Collection reads all refs without Git's committer-date
limits so rebased or imported commits keep their original author-date placement.
Filtering compares timezone-aware instants and is independent of the host zone.
Large local histories require a full history read, subject to the command timeout.
Caches collected with the old date prefilter are recollected automatically.

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

Caches store a schema version and exact collection inputs: normalized real source
path, dates, weeks, timezone, GitHub owner, and collection policy. Equivalent
relative/absolute source paths share an identity; different source directories
use separate cache files. Missing, incompatible, or malformed cache envelopes
are recollected. Same-input caches are snapshots until `--refresh` or an interval
change; refresh after local history or GitHub access changes.

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

Install development tools in the active Python environment and Node.js 22+:

```powershell
python -m pip install -r requirements-dev.txt
npm ci
npx playwright install chromium
```

Run the same checks used by CI:

```powershell
python scripts/run_tests.py
python scripts/check_risk.py
python scripts/check_mutations.py
npm run lint:python
npm run lint:markdown
actionlint
npm run test:browser
```

Use actionlint 1.7.12. CI installs that exact version through Go. The ordinary
`python -m unittest discover tests` command remains available, while the CI runner
also clears GitHub credentials and rejects accidental external commands or Python
network calls. Tests use temporary Git repositories and synthetic JSON fixtures.
The browser smoke test supplies pinned local copies of the existing chart libraries,
initializes both WebGL scenes and seven charts, and exercises table tabs and search.
Browser failures retain screenshots and traces under `test-results/browser/`.
Browser regression cases block each graphics dependency, disable WebGL, inject one
scene/chart failure, and open the local HTML with networking disabled. The dedicated
walkthrough test records a short video showing 3D fallback notices, working 2D charts,
and table filtering under `test-results/browser/`.

`.github/workflows/validate.yml` runs on pull requests, main pushes, and as a reusable
workflow. Its stable `Validation` status succeeds only if both platform test jobs
and the lint/browser and mutation jobs succeed. Main requires this status from GitHub Actions and
an up-to-date branch. Administrators are subject to the same gate; there is no routine
bypass. Any emergency protection change requires Franz's explicit authorization and
a recorded reason, followed by restoring the gate.

Pages calls the reusable workflow before building. Validation and report generation
check out the same immutable `github.sha`; failed or cancelled validation prevents
the build and artifact upload. The workflow does not inherit publication secrets
into validation jobs.

### Function risk and coverage

`python scripts/check_risk.py` runs fresh guarded tests with coverage.py 7.16.0
branch tracing, then measures cyclomatic complexity with Radon 6.0.1. It writes
`test-results/coverage.json`, `risk.json`, and a sorted `risk.md`; CI retains these
for seven days. All Python functions, methods, and closures under `src/` and in
`cli.py` are included, even when never imported or executed. Tests, development
scripts, module/class bodies, and embedded JavaScript are outside this function
metric. No `pragma: no cover` or partial-branch exclusions are applied.

CRAP is `complexity^2 * (1 - coverage)^3 + complexity`. Coverage is covered branch
outcomes divided by all branch outcomes, from 0 to 1; it is not coverage.py's
combined line/branch percentage. A function without branch outcomes uses statement
coverage, explicitly identified in the report, so an unexecuted function does not
receive vacuous 100% coverage. Subprocess execution is not credited; the guarded
suite exercises production functions in-process.

Scores above 30 are actionable; scores from 15 through 30 form the review queue.
`quality/risk-baseline.json` records the initial three legacy exceptions and the
worst score, with exact unrounded values. The gate rejects a new score above 30,
an existing exception above its cap, or any worst score above its baseline. Legacy
exceptions remain marked actionable in every artifact. Lower the affected caps
when improving their measured risk; never raise them as a routine way to pass CI.
Baseline changes require the same PR review as code. A renamed high-risk function
has no legacy exception. Low averages cannot hide a failing function.

The gate tests exercise formula boundaries, new high risk, legacy and worst-score
regressions, untested branchless code, and missing measurement data. To check a
real negative control, temporarily add an untested function with six independent
`if` statements under `src/`, run the measurement command, and confirm exit 1 and
an actionable entry. Remove the probe and rerun before committing.

See [coverage.py branch measurement](https://coverage.readthedocs.io/en/latest/branch.html)
and [Radon complexity](https://radon.readthedocs.io/en/latest/intro.html#cyclomatic-complexity)
for the maintained tools' definitions. CRAP is a prioritization signal, not proof
of correctness; mutation and browser-specific gates are tracked separately.

### Mutation qualification

`python scripts/check_mutations.py` uses Cosmic Ray 8.7.0 on Python 3.12 and runs
the guarded suite in a disposable copy. It first requires the unmodified tests
to pass, then replaces the median assignment with `-999.0` and requires a failure
in the median behavior assertion. It restores that copy before the normal run.
The worktree's production files are never mutated.

`quality/mutation-policy.json` declares the initial scope: PR/issue rates,
average and median cycle times, cycle-duration buckets, interval membership,
date-range construction, and cache-envelope matching. Targets follow named AST
functions and assignments; missing or ambiguous targets fail. All Cosmic Ray
core operators in those spans are retained. Other code is explicitly outside
this score; no individual survivor is suppressed as equivalent.

The break threshold is **80%** and the target is **90%**. Score is completed kills
divided by all selected mutants, including survivors, timeouts, errors, and pending
work in the denominator. Timeouts do not count as kills; errors, pending work,
and an empty run fail regardless of score. Each mutant has a five-second timeout.
The local distributor runs serially; allow several minutes for a complete run.

The initial measurement before the new behavior assertions was **57.94%**:
186 killed, 135 survived, zero timeouts/errors/pending, and 1,013 mutants excluded
because they were outside the selected spans. All 321 selected mutants ran, and
the command correctly failed below 80%. The negative-median control was killed.
The final score is published in each CI artifact; the new tests cover fractional
rates, precise averages, all duration-bucket boundaries, empty activity, inclusive
interval endpoints, full-day date ranges, and strict cache completeness.

The required `Mutation qualification` job writes a seven-day
`test-results/mutation/results.json` artifact with policy, counts, score, and each
mutant's module, line, operator, and outcome. It excludes raw source diffs and test
output. Surviving mutants remain visible and are the next assertion-review queue.
This is a score for the declared targets, not a repository-wide mutation score.
Keep the break and target thresholds under normal PR review; improve tests or
explain an explicit scope change rather than lowering the gate to hide survivors.

To re-evaluate a saved artifact against the current threshold without rerunning
mutations, use `python scripts/check_mutations.py --check-report <results.json>`.
This only checks that saved result; it does not qualify the current source. The
initial 57.94% artifact was rechecked this way and returned exit 1. CI always uses
the fresh full-run command. See the maintained
[Cosmic Ray documentation](https://cosmic-ray.readthedocs.io/en/latest/).

## Requirements

- Python 3.10+ and the pinned `tzdata` package in `requirements.txt`.
- GitHub CLI (`gh`) authenticated with repository access.
- Local repository clones in `D:\github\HemSoft` (automatically cross-referenced with GitHub remote metadata).
