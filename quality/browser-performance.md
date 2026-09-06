# Browser performance qualification

Run in a dedicated terminal with the repository's Python virtual environment on
PATH, development requirements installed, `npm ci` complete, and Playwright
Chromium installed. Close unrelated heavy workloads for comparable local runs.

```sh
npm run test:budget
npm run benchmark:probe
npm run benchmark
npm run benchmark -- --full
```

The normal command is the required PR check: small reports at 320px/DPR 1 and
390px/DPR 2, and large reports at 1024px/DPR 1 and 1440px/DPR 2. Each case has
three independent browser contexts, for 12 samples. The full command covers both
sizes at all four widths and both DPRs, with five repetitions: 80 samples.
Heights are 844px on phones, 768px at 1024px, and 900px at 1440px.
The scheduled Sunday backstop runs the full matrix. Job limits are 15 minutes
for PRs and 45 minutes for the full run; artifacts remain available for 14 days.

## Fixtures and measurement

Fixtures use the production analyzer and template, with no GitHub collection or
cache access. Small means 12 weeks, 20 repositories, 1,200 commits, 200 PRs, and
100 issues. Large means 52 weeks, 200 repositories, 20,000 commits, 2,000 PRs, and
1,000 issues. Both include the application's existing display limits of 50 recent
PRs and 100 recent commits. All repository profiles and weekly buckets are rendered.
Fixture dimensions and generated HTML byte counts are included in each report.

Chromium runs headless with SwiftShader software WebGL. Scripts come from pinned
local npm bytes with their production SRI attributes; fonts and avatars use the
existing deterministic test responses. These results measure browser work without
network latency. They are not physical-device or hardware-GPU performance claims.

Each sample measures navigation until all seven charts and both WebGL renderers
initialize. A resize/hover/rotation/reset/tab/filter workload runs before a 1.5s
warm-up. Resize uses actual viewport changes; hover, clicks and input dispatch
DOM events to the real handlers in one browser evaluation. This avoids measuring
Playwright actionability waits as workload cost; the separate browser tests cover
human-style interaction. After forced collection, an idle animation window of at
least 1.5s and 30 intervals records raw RAF
intervals, their p95, main-thread task time, and per-process CPU time. Browser
task duration uses wall time and can include blocking; it is not CPU usage.
Process CPU comes from cumulative CPU seconds across all process threads, divided
by the elapsed interval between the two CDP samples. A value of 2 means roughly
two CPU cores, including when the process is the software GPU process.
Browser
processes are reused between fresh contexts; first-navigation/JIT variation stays
visible in the samples. Forced collection and the harness add overhead, so these
numbers are diagnostic measurements rather than user-perceived timings.

Three workload cycles follow in PR mode, five in full mode. Every cycle ends in
forced collection and a resource snapshot. Each snapshot separates:

- V8 managed heap, document, DOM-node, and listener counts from CDP.
- Scene geometry/material allocations from renderer upload, texture, and program
  counters. A newly visible existing geometry can upload lazily without being a
  newly allocated scene object.
- Per-process RSS/VMS and cumulative CPU for this benchmark browser, including its
  renderer and GPU process. Summed RSS includes shared pages and managed memory;
  it is not an isolated native-memory measurement. GPU-process RSS is not VRAM.
- GPU VRAM, which is explicitly unavailable (`null`) in this harness.

Raw samples record revision, dirty status, environment, source hashes, rendering
backend, and process IDs. CI's clean checkout provides revision-linked artifacts;
local dirty measurements must be identified as such. Compare repeated runs on the
same browser build, operating system, hardware, and backend before interpreting
a change. RSS fluctuations or a few retained samples alone do not establish a leak.

## Gates and interpretation

`browser-budget.json` holds reviewed upper bounds. Every sample must meet the
policy. `browser-baseline.json` preserves the first qualified hosted run's
environment, fixture sizes, per-case variance, and memory maxima beyond artifact
retention. It names its exact source run/revision and accounting limits. Compare
like environments; update the reference only through review. Every sample must meet the
initialization, frame-p95, absolute heap/RSS, and retained-growth bounds. Missing
measurements, missing/duplicate cases, incomplete repetitions, browser errors,
or unavailable required process memory fail qualification. Frames are checked
from raw intervals. Scene allocations, textures, programs, listeners and document
counts cannot grow after warm-up; DOM nodes have a small allowance for UI state.
Uploaded geometry may increase only within the measured scene allocation count.

The initial caps are 10s initialization, 1000ms frame p95, 25MB V8 heap, 4MB retained
heap growth, 1.5GB summed process RSS and 256MB RSS growth. These are coarse
regression limits for software rendering on hosted runners, not UX targets.
Task wall time and process CPU remain reported diagnostic values: the software GPU
process can already saturate the hosted runner's CPU allocation, so a CPU
non-regression percentage cap has little useful headroom.
Frame time and memory still expose further deterioration. Review measured
per-case ranges and variance alongside gate status; do not use a passing aggregate
to claim a smooth high-DPR experience.

The first hosted qualification of unchanged rendering measured 567-700ms frame
p95 in large cases and failed the provisional 500ms exploratory cap. The initial
software-runner cap was therefore calibrated to 1000ms before adoption. The
retained-heap break threshold stayed at 4MB throughout qualification and the
negative probe. Sampling now requires at least 30 intervals (with a 45s deadline),
because a 1.5s-only window produced too few frames on the saturated runner.

The disposable probe retains a large JavaScript array after each workload cycle.
CI requires an actual exit 1 with a retained-heap violation, saves its result,
and then runs the clean benchmark against unchanged budgets. Unit checks also
exercise slow frames, retained scene allocations, RSS growth, missing samples,
and unavailable process memory. Never raise a cap merely to make a regression
pass. Explain an environment change or investigate the affected sample first.

`node scripts/check_browser_budget.js <results.json>` checks a saved artifact
against the current policy; it does not measure current source. `--record-only`
records exploratory results and violations without enforcing budgets, and is
never used in CI. An execution error still fails this mode.

Definitions: [CDP Performance](https://chromedevtools.github.io/devtools-protocol/tot/Performance/),
[CDP process CPU](https://chromedevtools.github.io/devtools-protocol/tot/SystemInfo/#type-ProcessInfo),
and [psutil memory fields](https://psutil.readthedocs.io/en/latest/#psutil.Process.memory_info).
