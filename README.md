# HemSoft productivity audit tool

Automated audit reporting engine for engineering throughput, pull request velocity, code churn, and temporal cadence across `github.com/HemSoft` repositories.

Local collection defaults to the personal HemSoft account. Set
`REPORT_GITHUB_OWNERS` to a comma-separated owner list to include organization
repositories. The Pages build uses `HemSoft,hemsoft-dev`, preserving coverage
of retained personal repositories through the organization transfer. Every owner
is enumerated completely; duplicate repository basenames across selected owners
stop collection before cloning rather than mixing their activity. Cache reuse
requires the same owner list. Repository and commit links use the collected
canonical identity; archived editions retain their original links.

The main-only **Verify organization reporting credential** workflow verifies
the existing `REPORTS_PAT` belongs to HemSoft, has classic `repo` scope and can
read the designated private organization pilot. It performs GET requests only
and never prints credential values. An unsuccessful verification remains a
mandatory gate in [SFL migration #138](https://github.com/HemSoft/set-it-free-loop/issues/138).

The tool generates standalone interactive HTML dashboards with Three.js 3D bar models and Chart.js analytics.

## Output

- Primary report location: `D:\hemsoft-productivity.html`
- Single HTML file with embedded report data, CSS and the Three.js graphics bundle; Chart.js loads from a CDN.
- No local server required. Open directly in any modern browser.

Productivity editions use the HemSoft Reports mark, charcoal surfaces, gold
controls and system fonts. Data series retain distinct colors and addition/deletion
values retain their semantic colors. The generator applies this identity to each
new edition; archived editions keep the presentation they were published with.

The seven Chart.js charts require access to `cdn.jsdelivr.net`. Three.js and
OrbitControls are bundled in the HTML and work offline. Typography and branding
require no external font or avatar requests.
3D views require WebGL 2. The generated file is not a fully bundled offline app.

If a visualization library is blocked or graphics initialization fails, each affected
view displays an unavailable notice. A failed scene or chart leaves the independent
views running; unavailable 3D controls are disabled. With networking disabled,
embedded metrics, repository/PR/commit tables, tab navigation, and filtering still
work. Outbound GitHub links require connectivity.

Each of the nine visualizations has a named region and a **View ... data** disclosure.
Press Enter or Space on its summary to inspect a captioned table, even if graphics
are unavailable. Weekly tables include every plotted value and hover detail, plus
cumulative additions; the cadence table exposes all 168 day/hour values in
`America/New_York`. Repository and language alternatives match the charts' top-eight
and top-seven subsets. Focus a wide table's scroll region and use arrow keys to pan.

Auto-rotate buttons expose their pressed state and identify the scene they control.
The report table tabs support Left/Right, Home, and End keys, with automatic activation
and a single tab stop. Tab then reaches the named search field; its filter applies to
the selected table. Keyboard focus has a visible outline.

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
├── publish.py           # Adds editions to the site and rebuilds the index
├── src/
│   ├── collector.py     # Git numstats, worktree deduplication, and GitHub API queries
│   ├── analyzer.py      # KPI aggregation, 7x24 matrices, and PR cycle times
│   ├── template.py      # Standalone HTML dashboard generator with 3D/2D visualizers
│   ├── generator.py     # End-to-end orchestration, cache management and edition output
│   ├── catalog.py       # catalog.json, edition manifests and publishing
│   └── landing.py       # HemSoft Reports index page built from the catalog
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

The header displays the data's `generated_at` timestamp in `America/New_York`,
including EST/EDT and its UTC offset. Reusing a cache preserves that timestamp;
rendering HTML does not make old data fresh. Missing timestamps display `Unknown`,
and timestamps without an offset are rejected. Cadence labels use ET because a
selected period can span both standard and daylight saving time. The under-one-hour
percentage uses merged PRs with measured cycle times, matching the chart buckets;
no measured cycles displays 0.0%.

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

The Pages site is **HemSoft Reports**, an index of every report HemSoft publishes.
Reports don't need to have anything in common. Each published copy of a report is
an *edition*, and every edition stays on file with the data behind it.

```text
catalog.json                              every report and edition (the source of truth)
index.html                                landing page, rebuilt from catalog.json
reports/<report>/index.html               redirect to the report's latest edition
reports/<report>/<edition>/index.html     the edition's HTML
reports/<report>/<edition>/payload.json   the edition's data
```

The site lives on the orphan `published` branch. A scheduled workflow
(`.github/workflows/pages.yml`) publishes a new productivity edition every
Monday at 08:00 EDT / 07:00 EST, commits it to `published`, and deploys the
branch to Pages. Manual runs are available from the Actions tab. Rerunning on the
same day replaces that day's edition.

### Publishing any report

A report joins the index when it publishes its first edition. Write the report
as one HTML file and its data as JSON, then describe the edition in a manifest:

```json
{
  "report": {
    "id": "ops-review",
    "title": "Operations Review",
    "summary": "Incidents, deploys and on-call load.",
    "category": "Operations",
    "cadence": "Weekly"
  },
  "edition": {
    "id": "2026-10-05",
    "title": "Week 40",
    "period": { "start": "Sep 29, 2026", "end": "Oct 05, 2026" },
    "highlights": [{ "label": "Incidents", "value": "0" }]
  },
  "files": { "html": "report.html", "payload": "payload.json" }
}
```

Report and edition ids are lowercase slugs (`a-z`, `0-9`, `-`); they become URL
folders. `category`, `cadence`, `edition.title`, `period` and `highlights`
(up to six label/value strings, shown on the index) are optional. File paths are
relative to the manifest. Then publish into a checkout of the `published` branch:

```powershell
python publish.py add site --manifest edition/manifest.json
python publish.py build site
```

`add` validates the manifest and payload JSON, copies both files into
`reports/<report>/<edition>/`, and records the edition in `catalog.json`.
`build` rebuilds `index.html` and the redirects from the catalog. The productivity
report writes its own manifest with `--edition-dir`:

```powershell
python cli.py --weeks 12 --edition-dir edition
```

That folder holds `report.html` (with an **All reports** link back to the
index), `payload.json` (the same analytics as `--json-out`) and `manifest.json`.

### Static report editions

Checked-in static reports live under `editions/<report>/<edition>/`, with
`report.html`, `payload.json` and `manifest.json`. Import them before rebuilding:

```bash
python publish.py sync site --editions editions
python publish.py build site
```

The Pages workflow runs this import alongside the productivity edition. Repeated
imports preserve each static edition's first publication timestamp, update its
HTML and JSON, and retain all other archived reports. Missing source folders or
invalid manifests stop publication.

The [Dune: Awakening loot reference](https://hemsoft.github.io/reports/reports/dune-awakening/2026-10-05/)
is a snapshot checked on October 5, 2026. Its 192 schematics, community tier
ratings, station memberships and chest chances remain as supplied. Search,
filters and the embedded Geist font work offline. The report links back to the
catalog and provides its [JSON payload](editions/dune-awakening/2026-10-05/payload.json).
Its [research notes](editions/dune-awakening/2026-10-05/sources.md) explain the
source dates, ranking caveats and item alias. It publishes at
`reports/dune-awakening/2026-10-05/`, with `reports/dune-awakening/` opening the
latest edition. Adding a future snapshot uses a new edition folder and manifest.

The index lists published reports in a table with Name, Link and Date created
columns. Report links open the latest edition. Date created is the earliest
recorded publication timestamp for that report, displayed in Eastern time
(`America/New_York`). Expand **Archived editions** to open any edition or its JSON
payload. The directory uses native HTML tables and disclosure controls without
JavaScript or external fonts.

### One-time setup

1. For collection across HemSoft and hemsoft-dev, use a classic PAT owned by
   HemSoft with `repo` scope and organization access, saved as the `REPORTS_PAT`
   repository secret. A fine-grained PAT has one resource owner and cannot cover
   both accounts in this workflow. Classic `repo` scope includes write capability;
   the collector and verifier use only read operations and cloning. Keep the token
   confined to those steps. The workflow stops when it is missing or a repository
   cannot be cloned. Run **Verify organization reporting credential** on main to
   prove the configured access before migration.
2. Enable Pages: repo Settings -> Pages -> Build and deployment ->
   Source: GitHub Actions.
3. Run the workflow once via Actions -> Publish reports to GitHub Pages ->
   Run workflow, then open the Pages URL.

Repository discovery follows every GitHub GraphQL cursor for repositories owned
by each configured owner and accessible to the authenticated account. PR and issue histories
are paginated in full, then filtered by creation, closure, or merge events in the
selected interval. Activity without commits still appears in metrics and profiles.
Duplicate records, changing totals, GraphQL errors, missing pages, or stalled
cursors stop collection. A token cannot reveal repositories it cannot access;
use credentials covering the intended repository set. Large histories require
more API requests, and rate-limit failures remain explicit.

The `build` job clones all discovered repos from both configured owners into `checkouts/` and runs
`python cli.py --weeks 12 --base-dir ./checkouts --edition-dir ./edition`. The
`archive` job, the only job with `contents: write`, holds no PAT. It adds that
edition to the `published` branch, rebuilds the index, pushes the branch, and
uploads it as the Pages artifact. `checkouts/` and `edition/` are build outputs.

The repository remains private, but the Pages site and its exported metrics
are public. Private repository visibility does not restrict access to the site.

## Running tests

Install development tools in the active Python environment and Node.js 22.22.2
or a later 22.x release, matching the CI runtime:

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

Markdown linting uses `markdownlint-cli` with the existing rules and exclusions.
The former CLI2 dependency chain included an unpatched `braces` vulnerability.
The npm overrides pin patched YAML, Markdown, TOML, and math-parser dependencies;
keep them until the CLI's dependency ranges select audited versions without them.
CI still rejects every advisory reported by `npm audit --audit-level=low`.

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
Accessibility tests compare every alternative-table value with the fixture, inspect
the browser accessibility tree for cadence row/column headers and all 168 cells,
exercise keyboard controls, and run pinned axe-core checks on visualization regions
and the table toolbar. CI retains the accessibility tree, scan result, screenshot,
and keyboard walkthrough for seven days. These checks cover the report's chart data
and controls; they do not replace testing with a user's preferred screen reader.

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

`python scripts/check_risk.py` runs fresh guarded tests with coverage.py branch
tracing, then measures cyclomatic complexity with Radon. Tool versions are pinned
in [requirements-dev.txt](requirements-dev.txt); `risk.json` records their installed
versions. It writes
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

## Responsive report layout

The header, visualization controls, table tabs, and search wrap within the page.
At phone widths, the header stacks and controls retain at least 44px height.
Wide data tables scroll inside their own containers; the page does not hide
horizontal overflow to conceal clipped content. Names keep their normal font size.

Browser validation checks 320x844, 390x844, 1024x768, and 1440x900 CSS viewports,
including keyboard focus, expanded data tables, element bounds, and document width.
CI retains header, scene, and table screenshots with geometry JSON for seven days.
The mobile video demonstrates visible header actions, keyboard rotation control,
local cadence-table scrolling, tab selection, and filtering at 320px.

## Dependency integrity and security checks

External Actions use full commit SHAs with major-version comments. Weekly
Dependabot PRs cover Actions, npm, and pip dependencies. Review upstream release
notes and the exact commit diff before accepting an Action update; verify that
the revision belongs to the official `actions/*` repository. The local policy
check rejects mutable references and unexpected job permissions. Pages build has
only `contents: read`; only deployment can write Pages and request an OIDC token.
Checkout does not persist credentials in the build or security job. Keep
`REPORTS_PAT` confined to the collection and read-only verification steps. Its
classic `repo` scope is broader than the operations performed by these steps.
Pages packaging follows the official upload-pages-artifact tar format, then
uploads `artifact.tar` as `github-pages` with the pinned upload-artifact action.
This avoids the mutable nested `upload-artifact@v4` reference in the v3 wrapper.

Both executable library scripts require SHA-384 Subresource Integrity (SRI) and
anonymous CORS. Chart.js bytes match the exact npm version in `package-lock.json`.
The security gate also compares browser URL versions with the declared, locked,
and installed npm versions. Matching bytes alone must not hide a stale CDN URL.
The Chart.js URL deliberately uses the package's UMD file, avoiding a CDN-only
minification transform. For a browser-library update, update the npm pin/lock,
script URL, fixture mapping, security-check inventory, and SRI together. Compare
downloaded bytes with the
installed package, calculate `sha384-` plus the Base64 SHA-384 digest, then run
every browser test. Do not remove SRI to make an update pass. Two regression
cases alter the CDN response or embedded bundle and require browser rejection, no injected-code
execution, and usable fallback content. Productivity reports use system fonts
and the embedded HemSoft mark, with no external font or avatar requests.

Three.js and its ESM OrbitControls addon are built from the pinned npm package
with pinned esbuild into `assets/report-graphics.js`. The upstream MIT license
is retained. The committed manifest records versions, byte count and SHA-384.
`npm run assets:build` regenerates both files; `npm run assets:check` rebuilds in
memory and rejects any difference. Python verifies the manifest and embeds an
integrity-protected data URL, so report generation and Pages need no Node runtime.
When updating Three.js, regenerate the bundle, commit both outputs, and run all
browser and performance checks. The security job performs the fresh-build check.

Install `requirements-security.txt` alongside the development requirements, then
run these same commands used by the required security job:

```sh
python scripts/check_security.py
python -m unittest discover tests/security
python -m pip_audit -r requirements-dev.txt -r requirements-security.txt
npm audit --audit-level=low
```

The first command checks policy, runs detect-secrets in UTF-8 mode on Git-tracked
files with network verification disabled, and runs Bandit on Python production and tool
scripts. Potential secrets fail without printing values. Bandit fails on medium
or high severity; low-severity findings remain visible in its counts and need
manual review. It does not analyze embedded JavaScript. No source or secret
values are suppressed except the two verified public SRI digests and the exact
generated vendor file, after its bytes and manifest match a fresh pinned build.
Other tracked files remain scanned. An altered digest or bundle fails before scanning.
No source or secret
values are uploaded to an analyzer. pip-audit and npm audit send public package
names/versions to their advisory services; dependency installation also uses
package registries. All reported dependency vulnerabilities fail the gate, and
network/tool failures also fail. Checks cover current tracked content and known
advisories, not Git history or proof that dependencies are harmless.

Tool references: [GitHub Action pinning](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/find-and-customize-actions),
[detect-secrets](https://github.com/Yelp/detect-secrets),
[Bandit](https://bandit.readthedocs.io/en/latest/man/bandit.html), and
[pip-audit](https://github.com/pypa/pip-audit).

## Browser performance and resources

The required browser benchmark uses representative small/large reports, repeated
warm samples, retained-resource checks and a controlled failing allocation probe.
A weekly full viewport/DPR matrix supplies the more expensive backstop. Read the
[method, budgets, commands and measurement limits](quality/browser-performance.md)
before comparing results or changing a budget.

## Requirements

- Python 3.10+ and the pinned `tzdata` package in `requirements.txt`.
- GitHub CLI (`gh`) authenticated with repository access.
- Local repository clones in `D:\github\HemSoft` (automatically cross-referenced with GitHub remote metadata).
