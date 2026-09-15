# Testing

Tests are `pytest`, organized per module under `tests/<module>/`. Config lives in
`pytest.ini` (`testpaths = tests`, marker registry) and `.coveragerc` (branch coverage
over all module source, excluding `*/tests/*`, `*/.venv/*`). `pytest.ini` is the single
source of truth — do not re-add `[tool.pytest.ini_options]` to `pyproject.toml`, it
loses to `pytest.ini` and silently drifts.

Use the venv interpreter: `./.venv/bin/python -m pytest …`.

## Test layers

| Layer | What it covers | Needs |
|-------|----------------|-------|
| **Unit** | `core/` logic — catalog build, config, parsers, prompt wrapping, aggregation, ONNX surgery, accuracy math | nothing (stdlib) |
| **Contract** | `server.py` routes against a live in-process server on an `18xxx` test port; i18n key parity; tutorial 6-lang; shared base handler / chat engine | nothing |
| **i18n audit** | `tests/i18n_audit/` — copy inventory, missing-language, integrity, runtime lang-hook gaps, Spanish/stale-copy coverage | nothing |
| **Browser** | Playwright copy audit + language-switch matrix (optional; scripts under `scripts/`) | `playwright` install |
| **E2E (mock)** | `tests/e2e/` inference triple gate — UI click -> `/api/run*` -> rendered result -> perf numbers, against a fixture `DX_APP_ROOT` + shell fake runner | `playwright` + a chromium |
| **E2E (NPU)** | the same triple gate against real DX-M1 inference | NPU + `DX_E2E_NPU_MODEL` |
| **E2E (other)** | real compile / real CLI agents | `dx_com`, dx-runtime, or CLIs |

Live-server tests bind a **`18xxx` port = `1` + the real port** (e.g. dx_app → 18080,
dx_agent_dev → 18099) so they never collide with a running studio instance.

## Running the suites

Run module suites **separately** — do not run `tests/launcher/` and
`tests/dx_agent_dev/` in a single pytest invocation (their live servers collide on the
`18xxx` range).

```bash
./.venv/bin/python -m pytest tests/launcher/ -q          # ~521 tests
./.venv/bin/python -m pytest tests/dx_agent_dev/ -q      # ~228 tests (run alone)
./.venv/bin/python -m pytest tests/dx_app/ -q
./.venv/bin/python -m pytest tests/dx_stream/ --ignore=tests/dx_stream/benchmark -q  # ~273
./.venv/bin/python -m pytest tests/dx_compiler/ -q
./.venv/bin/python -m pytest tests/dx_modelzoo/ -q
./.venv/bin/python -m pytest tests/dx_planner/ tests/dx_benchmark/ tests/dx_monitor/ -q
./.venv/bin/python -m pytest tests/i18n_audit/ tests/shared/ tests/release/ -q
```

### Special test areas

- **`tests/dx_stream/benchmark/`** — requires the sibling `dx-runtime/dx_stream` tree
  on `sys.path`. If absent it no-ops (skips, ~121 tests). Excluded above via `--ignore`.
- **`tests/dx_modelzoo/`** — the generated catalog is gitignored; the conftest
  bootstraps it, or generate manually:
  `./.venv/bin/python dx_modelzoo/tools/sync_metadata.py --offline`.

### Markers (`pytest.ini`)

`requires_node`, `requires_pillow`, `requires_dx_runtime`, `external`, `smoke`, `e2e`,
`help_audit`. Skip environment-dependent tests, e.g. `-m "not requires_dx_runtime"`.

## Gates

There is no `.github/workflows/` in this repo — the real gate is `scripts/run_ci.sh`.
The parent suite invokes it from `dx-all-suite/.github/workflows/dx-ai-studio-pytest.yml`,
which triggers on `pull_request` for `dx-ai-studio/**` and runs on a `self-hosted` `sdk`
runner. (The heavier i18n smoke matrix lives in `dx-ai-studio-i18n-audit.yml` and is
`workflow_dispatch`-only — too slow to block a merge.) `run_ci.sh` runs seven numbered
stages in order:

```bash
bash scripts/run_ci.sh
```

```
--   CSS token ratchet — scripts/css_token_gate.py (runs before stage 0/7)
--   i18n lang-span ratchet — scripts/i18n_span_gate.py
--   breakpoint ratchet — scripts/breakpoint_gate.py
0/7  Infra + release contracts — tests/test_pytest_infra_contract.py,
     tests/shared/test_ci_contracts.py, tests/shared/test_studio_version_contracts.py,
     tests/release/
1/7  Collection gate — tests/ --collect-only, must report 0 collection errors
     (--ignore=tests/dx_stream/benchmark, tests/e2e, and the Playwright browser tests)
2/7  Launcher suite (isolated — port collision with dx_agent_dev)
3/7  Agent Dev suite (isolated — port collision with launcher)
4/7  i18n audit gate — bash scripts/i18n_audit_gate.sh
5/7  Module + shared + root contract suites (no browser) — dx_app, dx_stream,
     dx_compiler, dx_modelzoo, dx_planner, dx_benchmark, dx_monitor, shared,
     i18n_audit, tests/test_*.py
6/7  Inference E2E triple gate — tests/e2e/ -m e2e_mock, in its OWN pytest process
     (its conftest rebinds DX_APP_ROOT at import time)
```

### The inference E2E triple gate (`tests/e2e/`)

One browser journey — open Run, pick category -> model -> sample image, click Run —
asserted on three independent layers so a regression in any one fails the gate:

1. **network** every `/api/run*` response is HTTP 200 and the terminal payload has
   `exit_code == 0` and no `error` (the UI prefers async `/api/run_async` + polling,
   with a blocking `/api/run` fallback; both are covered)
2. **render** the result image is visible AND `naturalWidth > 0` (proves the browser
   decoded the base64 JPEG — a corrupt `src` stays "visible" but is zero-wide)
3. **metrics** the FPS and Latency perf cards carry finite, in-range numbers

`tests/e2e/fake_app_root.py` builds a throwaway `DX_APP_ROOT` (registry, a stub
`.dxnn`, a sample JPEG, and a POSIX-shell fake runner). Because `DX_APP_ROOT`,
`BUILD_DIR` and `DXAPP_SAVE_IMAGE` are already env-driven, **no production code is
modified** — only the NPU binary is swapped, so the real `subprocess.Popen`, the real
`_parse_perf`, the real result-image pipeline and the real `/api/run` route all run.

#### The real-NPU tier

`DX_E2E_NPU_MODEL` is a **registry name** from dx_app's `config/test_models.conf`
(e.g. `yolov11n`), not a filename. The tier skips — with the specific reason — when
the model is unknown, `/dev/dxrt0` is absent, or no `.dxnn` can be found.

```bash
# The model is already installed (dx_app setup.sh has run): the real tree is used.
DX_E2E_NPU_MODEL=yolov11n ./.venv/bin/python -m pytest tests/e2e/ -m e2e_npu -q

# The .dxnn lives elsewhere — e.g. a ModelZoo download cache. dx_app/assets/ is
# root-owned on a provisioned board, so instead of needing sudo to drop a model in,
# the fixture builds a symlink overlay and leaves the runtime tree untouched.
DX_E2E_NPU_MODEL=yolov11n \
DX_E2E_NPU_MODEL_FILE=../workspace/res/models/yolo11-n_640x640.dxnn \
  ./.venv/bin/python -m pytest tests/e2e/ -m e2e_npu -q
```

Which root a process gets is decided ONCE at conftest import, because
`dx_app.core.config` freezes `BUILD_DIR`/`CATEGORIES` on first import. The two tiers
therefore cannot share a pytest process — run them as separate invocations, which
`run_ci.sh` already does (stage 6 is `-m e2e_mock`).

The NPU test also asserts its FPS/latency are **not** the fake runner's constants,
so a misconfiguration that silently falls back to the mock cannot report a green
"NPU verified".

Extra flags: `--browser` (adds the Playwright copy/lang-switch/tutorial suites,
needs `chromium` installed), `--ux` (full UX acceptance gate, slow, release only).

### Cross-browser

Engine selection is env-driven — `DX_BROWSER_ENGINES=chromium,firefox[,webkit]`.
The default is **chromium alone**, so the blocking gate stays single-engine and fast;
the advisory CI job opts into firefox.

> **Scope today: `tests/e2e/` only.** The ten legacy browser suites listed in
> `run_ci.sh` call `pw.chromium.launch()` inside their own fixtures, so they run on
> chromium no matter what `DX_BROWSER_ENGINES` says — the gate labels them
> `(chromium)` rather than claiming coverage they do not have. To migrate one, replace
> its fixture's `pw.chromium.launch(headless=True)` with
> `tests.browser_support.launch_browser(pw, engine)` and parameterise on
> `selected_engines()`, the way `tests/e2e/conftest.py` does. Each migrated suite
> multiplies its own runtime by the engine count, so migrate the ones where
> rendering actually differs (zoom/layout audits) before the copy audits.

```bash
DX_BROWSER_ENGINES=chromium,firefox ./.venv/bin/python -m pytest tests/e2e/ -m e2e_mock -q
```

Only chromium falls back to a host binary (`google-chrome`). Playwright ships **patched**
Firefox/WebKit builds, so a distro Firefox is not a substitute — install them with
`python -m playwright install firefox webkit`. WebKit additionally needs distro packages
(`libevent-2.1-7t64`, `libavif16`) that only root can install; without them the suite
**skips** webkit with the driver's message rather than failing.

### Sharding

`--shard=i/N` splits the browser suites by **file** (each suite owns a sync-Playwright
event loop for its whole process, so a file cannot be split across workers). The i18n
copy audit is indivisible and is pinned to shard 1.

```bash
bash scripts/run_ci.sh --browser --shard=1/3
```

### Failure traces (Trace Viewer)

`tests/e2e/` records a Playwright trace for every test and keeps it **only on failure**
(`var/e2e-traces/<test>.<engine>.trace.zip`) — keeping traces for green runs would bury
the one that matters. CI uploads them as artifacts. Open one with:

```bash
playwright show-trace var/e2e-traces/<file>.trace.zip
```

### Coverage

```bash
./.venv/bin/python -m pip install pytest-cov   # not in requirements-ci.txt
bash scripts/run_ci.sh --coverage
```

Measures **all ten** shipped packages (it used to measure only `shared` + `launcher`,
which made eight well-tested modules look uncovered). The suites cannot share one pytest
process — launcher and dx_agent_dev collide on the `18xxx` ports and `tests/e2e` rebinds
`DX_APP_ROOT` — so it runs four groups with `--cov-append` and reports once.

**One source root, not ten.** `.coveragerc` sets `source = .` with `relative_files = True`,
and `run_ci.sh` passes a single `--cov=.`. This is not cosmetic: coverage.py strips whichever
declared root a file came from, so with ten roots every module's `server.py` rendered as
`filename="server.py"` and the nine distinct files **collapsed into one entry** in
`coverage.xml` — 9 files in the terminal report, 1 in the XML. Anything consuming that XML
(SonarQube) attributes the coverage to whichever root resolves first and reports the other
eight at 0%. A single root keeps the module in the path (`dx_app/server.py`), which is also
what `coverage_gate.py` splits on. A per-package `--cov=<pkg>` flag OVERRIDES the config's
`source`, so adding one back re-creates the collapse; `tests/shared/test_ci_contracts.py`
pins this.

`scripts/coverage_gate.py` then compares against `config/coverage_baseline.json`
(0.5%p tolerance). Report-only during the staged rollout; set `DX_COVERAGE_ENFORCE=1`
to make a drop fail. Refresh the baseline with `python scripts/coverage_gate.py --update`.

Baseline (`config/coverage_baseline.json`, branch coverage over 20,146 statements
across 152 files):

| module | cover | | module | cover |
|---|---|---|---|---|
| dx_planner | 91.7% | | shared | 74.8% |
| dx_benchmark | 91.2% | | launcher | 70.7% |
| dx_monitor | 85.0% | | dx_stream | 68.7% |
| dx_modelzoo | 83.8% | | dx_app | 68.2% |
| dx_agent_dev | 79.9% | | dx_compiler | 64.5% |

`dx_compiler` is still the thinnest, but the biggest wins are now per-FILE rather than
per-module — the module averages hide a few very large, very uncovered files:

| file | cover | uncovered statements |
|---|---|---|
| `dx_compiler/server.py` | 41.4% | 384 |
| `dx_stream/server.py` | 55.1% | 365 |
| `dx_app/core/live.py` | 17.3% | 337 |
| `launcher/launcher.py` | 67.2% | 334 |
| `dx_compiler/core/compiler_service.py` | 54.8% | 296 |
| `dx_app/core/modelzoo.py` | 28.5% | 206 |

The two `server.py` files and `compiler_service.py` are request handlers and dx_com
orchestration — reachable with the fake-subprocess / live-test-server treatment already
used by `tests/dx_compiler/test_setup_service.py` and `tests/dx_stream/test_server.py`.
`dx_app/core/live.py` drives camera/RTSP capture and needs either a fake capture source or
hardware. `dx_stream/core/webrtc.py` (42.7%) needs GStreamer GI bindings, which are absent
here.

Additional helper/manual checks, not part of `run_ci.sh`:

- `bash scripts/i18n_smoke_matrix.sh` — full i18n smoke incl. matrix.
- `bash scripts/i18n_browser_audit.sh` — optional Playwright copy audit.
- Server smoke (manual, not gated by `run_ci.sh`): confirm the launcher binds and
  prints its live banner — `./.venv/bin/python launcher/launcher.py --port 8890
  --no-browser`.
- Hardening checks: `DX_BIND_LOCAL=1 ./launcher.sh` (loopback only) and
  `DX_API_TOKEN=secret ./launcher.sh` (401 without a bearer token).

## SonarQube

`sonar-project.properties` is committed; the server is not configured in it. The endpoint
and credentials for the DEEPX SonarQube are not in any repository here, so they are passed
at scan time:

```bash
sonar-scanner \
  -Dsonar.host.url="$SONAR_HOST_URL" \
  -Dsonar.token="$SONAR_TOKEN" \
  -Dsonar.projectVersion="$(cat release.ver)"
```

`.github/workflows/dx-ai-studio-sonar.yml` does exactly that and is a deliberate **no-op
until the `SONAR_HOST_URL` / `SONAR_TOKEN` secrets exist** — every step that needs the
server is gated on a secret check, so the job reports success rather than failing every PR
on a guessed endpoint. It is advisory (`continue-on-error`) because a first scan of a
codebase this size surfaces a backlog, and blocking merges on it before that is triaged
just teaches people to ignore the gate.

Notes:

- **Coverage.** Sonar reads `coverage.xml` from `run_ci.sh --coverage`. That report is only
  usable because coverage now measures from a single root — see the Coverage section above.
- **Version.** Not in the properties file: `release.ver` is the SSOT and a copy would drift.
- **Exclusions.** The studio ships ~6 MB of JS, most of it vendored (`mermaid.min.js`) or
  generated (`i18n.js` is 5,175 lines with three functions — a translation table). Scanning
  it produces thousands of findings nobody will act on and buries the real ones.
- **Contracts.** `tests/shared/test_ci_contracts.py` pins that no endpoint or token is ever
  committed, that `sonar.sources` matches pyproject's package list, and that the report path
  is the one `run_ci.sh` actually writes.

### CSS token ratchet (`scripts/css_token_gate.py`)

Module CSS must take colour from tokens, not literal hex — a literal is invisible
to the theme switch, so it silently keeps the dark value on a light page. The gate
counts raw hex per module stylesheet and compares against
`config/css_token_baseline.json`:

```bash
python scripts/css_token_gate.py          # check (exits 1 on any increase)
python scripts/css_token_gate.py --write  # re-record after a reduction
```

The baseline can only go **down**. `tests/test_css_token_gate.py` enforces both
directions: `test_no_module_exceeds_its_baseline` fails on a new literal, and
`test_baseline_has_no_stale_headroom` fails when a file improved but the baseline
was not tightened — stale headroom would silently re-admit the literals you removed.

Baseline at the time the gate landed: **244 raw hex across 12 files**
(`sdk-library.css` 95, `launcher/style.css` 52, `dx_compiler` 20, `dx_app` 20, …).
`shared/static/` is deliberately out of scope — `dx-tokens.css` is where the
palette is *supposed* to live.

### i18n lang-span ratchet (`scripts/i18n_span_gate.py`)

A translatable label used to be written six times, once per language:

```html
<span class="ko">저장</span><span class="ja">保存</span>…<span class="es">Guardar</span>
```

Most of those strings also lived in the module's `_DX_I18N_DICT`, so a phrase had
two homes free to drift — and 125 keys had. The markup now carries
`data-i18n="English key"` and the dictionary owns every translation.

```bash
python -m scripts.i18n_span_gate          # check (exits 1 on any increase)
python -m scripts.i18n_span_gate --write  # re-record after a reduction
```

29 groups remain, pinned in `config/i18n_span_baseline.json`. They stay because one
key carries two different phrases and only a person can choose: `dx_stream` 'OK' is
'정상' (a status) in the dictionary and '확인' (a button) in the markup.

`config/i18n_key_gaps.json` pins the keys a dictionary cannot fill — the launcher's
`about*` labels come from `about-deepx.js` `ABOUT_NAV_LABELS`, not from
`_DX_I18N_DICT`. A key that falls back to English silently shows English, so the
gate refuses new ones.

`scripts/migrate_i18n_spans.py` performed the move and is kept for the remainder.
It reports before it writes and never invents a translation: where markup and
dictionary disagreed and the key was used nowhere else, the dictionary was corrected
to the markup so rendering stayed byte-identical.

### Breakpoint ratchet (`scripts/breakpoint_gate.py`)

Responsive layout splits at **19 different widths** (600, 640, 700, 720, 768, 769,
900, 960, 980, 1024, 1100, 1200, 1280, 1360, 1440, 1600, 1979 …). One screen folding
at 900 next to another folding at 960 is not a decision; it is a value copied from
whichever file was open at the time.

Moving those onto a scale changes how the product renders in each band, so the gate
does **not** move them. It refuses *new* values:

```bash
python -m scripts.breakpoint_gate          # check (exits 1 on a new width)
python -m scripts.breakpoint_gate --write  # re-record after a consolidation
```

Target scale is `600 / 900 / 1200 / 1440` (`SCALE` in the gate). Consolidate onto it
one file at a time, with the responsive baselines below as the check.

### Shared component ownership

`tests/test_shared_css_foundation.py` also tracks which stylesheets redefine a
component that `shared/static/dx-components.css` owns. Two allowlists carry the
current state, and a `..._has_no_stale_entries` test forces each entry to be removed
as the migration lands, so the lint keeps catching the next regression:

- `OWNED_COMPONENT_OVERRIDES` — shared owns the selector, a module overrides it
  (`.btn`: dx_benchmark, dx_planner).
- `UNOWNED_COMPONENTS` — no shared owner yet, modules each reinvent it
  (`.card`: dx_app, dx_benchmark, dx_monitor, dx_stream).

### Unified app shell (`tests/test_dx_shell.py`, `tests/shared/test_shell.py`)

`shared/static/dx-shell.css` + `shared/shell.py` render one skeleton (56px module
rail, 56px header, 42px page-tab row) that modules inherit. dx_app is the first
module on it. The contracts worth knowing about:

- The shell's markup is injected **server-side** (`DXBaseHandler.shell_spec` →
  `shared.shell.apply` inside `serve_template`), so any test that asserts on dx_app's
  header, toolbar or brand slot must read the **rendered** HTML, not the template —
  see `rendered_dx_app_index()` in `tests/test_shared_css_foundation.py`.
- Tab labels are never truncated. Overflow is a function of translation length, not
  window width (`Benchmark` is 9 characters in English and 25 in Spanish —
  `Evaluación de rendimiento`), so `shared/static/dx-tabs.js` moves whole tabs into a
  `+N` menu on both `ResizeObserver` and `dx-lang-applied`, and keeps the active tab
  in the row.
- `dx-shell.css` may not contain a literal colour; `dx-icons.svg` may not either
  (`currentColor` only) — both are theme-switch correctness, enforced by tests.

### Theme (`tests/test_dx_theme.py`)

`shared/static/dx-theme.js` holds three states — `dark`, `light`, `system` — under
`localStorage['dx-theme']`, mirroring the `dx-lang` convention. `system` removes the
`data-theme` attribute so `prefers-color-scheme` decides. `dx-theme-light.css` must
define **every** semantic token in **both** its blocks (`:root[data-theme="light"]`
and the `prefers-color-scheme` block guarded by `:not([data-theme="dark"])`); a token
present in only one block breaks solely for viewers on OS-light with no explicit
choice, which is the hardest case to notice by hand.

## Optional stages

`run_ci.sh` takes four opt-in flags. None of them run in the blocking PR gate.

| Flag | What it runs | Why it does not block |
|------|--------------|----------------------|
| `--npu` | `tests/e2e/ -m e2e_npu` — the triple gate against real DX-M1 inference | One board backs it; a merge must not depend on that board's health |
| `--visual` | `tests/visual/` — pixel diff vs committed screenshots | Baselines are per-host (font rasterisation differs) |
| `--browser` | the ten Playwright suites, shardable with `--shard=i/N` | Slow; advisory until the engines are stable in CI. **Currently red — see below** |
| `--coverage` | all ten `.coveragerc` sources vs `config/coverage_baseline.json` | Staged: visible, not yet gating |

### Real-NPU tier (`--npu`)

```bash
DX_E2E_NPU_MODEL=<registry name> bash scripts/run_ci.sh --npu
# model not under dx_app/assets/models (root-owned on a board)? add:
DX_E2E_NPU_MODEL_FILE=/path/to/model.dxnn
```

`--npu` exports `DX_E2E_NPU_STRICT=1`, which turns "no NPU / no model" from a skip
into a **failure**. pytest exits 0 when everything skips, so without it a scheduled
run on a board with a dead NPU would report green while proving nothing.

`--npu` runs the blocking stages first, and stage 6 (the mock tier) is invoked with
`env -u DX_E2E_NPU_MODEL -u DX_E2E_NPU_MODEL_FILE -u DX_E2E_NPU_STRICT`. That is
load-bearing: `tests/e2e/conftest.py` binds `DX_APP_ROOT` at import time and selects
the NPU overlay whenever `DX_E2E_NPU_MODEL` is set, so without stripping them the
mock tier looks for its fixture model in the real dx_app tree and the run fails its
own blocking stage (`model 'e2eyolo' is not in /api/models`).

It runs in CI from `dx-ai-studio-npu.yml`: nightly, on `workflow_dispatch`, and on a
PR labelled `run-npu`.

### Pixel visual regression (`--visual`)

`tests/visual/` screenshots every module's landing page across four axes and
compares each against a committed baseline:

| baseline | axes | shots |
|---|---|---|
| `<engine>/<module>__<theme>__<locale>.png` | 9 modules x {dark, light} x {en, es} at 1280x800 | 36 |
| `<engine>/<module>__w<width>.png` | 9 modules x {650, 860, 1150, 1320} at dark/en | 36 |

72 shots, 8.1MB. `tests/visual/baseline_spec.py` is the source of truth for the
axes and carries the reasoning for each one; do not restate the numbers here.

This is **not** what `tests/test_ux_visual_gate.py` does — that audits tutorial
spotlight geometry through the DOM. It catches "the highlight points at nothing";
it cannot catch "the header lost its border".

Determinism was measured, not assumed. With a fresh browser context per capture,
reduced motion, `animations="disabled"` and the tutorial TOC closed, repeat captures
of the same commit differ by **0 pixels** on all nine modules. Two findings shaped
the harness:

- **Reusing a browser context breaks it.** The second page in a context renders as a
  return visit (splash seen, panels remembered) — 48.8% of the launcher hub's pixels
  moved between two captures of the same commit until each got its own context.
- **Two modules need masks.** `dx_monitor`'s live telemetry drifts 0.0788%, and
  `dx_agent_dev`'s animated showcase thumbnails drift 0.97-2.16%. The latter only
  appears against a *stored* baseline — back-to-back captures agree — so it survived
  the first round of probing.

The threshold is 0.02% (`DX_VISUAL_MAX_RATIO`), chosen by measurement: at 0.1% a
global `--accent` change moved only one of nine modules past the limit. At 0.02% a
0.2px `letter-spacing` change is caught on **all nine**.

#### Axes

**Theme x locale.** A single-axis baseline could not see the token refactor:
semantic tokens and the light theme change *colour*, and translation length changes
*layout* (Benchmark -> "Evaluación de rendimiento" pushes the tab row into
overflow). `es` is the locale because its labels are the longest.

**Width.** The theme/locale shots are all captured at 1280, so moving a fold from
900 to 960 turns nothing red. `responsive_axes()` adds four widths at dark/en,
each sitting in the *middle* of a crowded band rather than on a boundary — on a
boundary a 1px difference flips the result and the gate goes flaky. Colour is not
what this axis watches, so one theme and one locale are enough.

These widths are the precondition the breakpoint ratchet was waiting on; see
`scripts/breakpoint_gate.py`.

#### What the green light does *not* cover

The capture seeds `dx-splash-seen` before loading (`tests/visual/conftest.py`), so
the intro never runs. That is deliberate — pixel-diffing an animation is not
deterministic — but it means a passing visual suite says "the page after the splash
did not move" and says nothing about the intro itself.

The intro is held by structural contracts instead, in
`tests/launcher/test_home_portal.py`: the grammar it obeys, the surface the light
crosses, the cut into the app, the reduced-motion path, the honesty of the working
beat, and the drawn scenes. A split of responsibility, not a gap.

Refresh baselines after an intentional design change:

```bash
DX_VISUAL_UPDATE=1 ./.venv/bin/python -m pytest tests/visual/ -q
```

## Pre-commit hook

The Node-free stand-in for the ticket's Husky step. Runs in ~4s on a normal commit.

```bash
bash scripts/install-hooks.sh     # symlinks scripts/pre-commit-hook.sh
git commit --no-verify            # bypass once
```

It checks only what is proportional to the staged diff — `py_compile` on `.py`,
`json.load` on `.json`, `bash -n` on `.sh` — plus `test_pytest_infra_contract.py`
and `test_ci_contracts.py`, which are what actually break when someone edits
`run_ci.sh`, `pytest.ini` or a workflow without updating its ledger. The full gate
stays in CI.

## Quarantined pre-existing failures

Stage 5/7 deselects one test that was **already failing before the PR gate existed**.
They are real content defects, not environment gaps, so they are NOT papered over with
skip guards — they are deselected in `scripts/run_ci.sh` (`QUARANTINE=(...)`) where they
stay visible and counted.

`tests/shared/test_ci_contracts.py` enforces three things: the list may only **shrink**,
every entry must be documented here, and a stale entry (test deleted/renamed) fails the
gate. So the debt cannot quietly grow.

| Test | Defect | Needs |
|------|--------|-------|
| `test_all_models_have_complete_legal_block` | The `yolo26-depth-*` family reaches the catalog from the dx_app source tree, not the ModelZoo sync snapshot, so it carries only `commercial_use: restricted` and no full legal block. | Upstream licence data. **Do not fabricate** — a wrong licence claim is worse than a missing one. |

#### `--browser` is red (2026-09-15)

`run_ci.sh` without flags reports zero failures, and that sentence has been quoted
as "everything is green". It is not: the browser suites are opt-in, so nothing in
the default run executes them, and `tests/test_tutorial_e2e_journey.py` has been
failing on three of its seven modules.

```
dx_modelzoo   download|step1   TARGET_MISSING  '[data-model-id][data-quant]'
dx_app        run-single|step9 TARGET_MISSING  '#r-topk'
              rundemo|step3    TARGET_MISSING  '#rundemo-block-0 [data-axis="post"]'
              rundemo|step4    TARGET_MISSING  '#rundemo-block-0 button[onclick*="rundemoRun"]'
              modelzoo|step4   TARGET_MISSING  '#mz-cart'
dx_agent_dev  showcase|step2   MOCK_INJECTION  data-dxt-tutorial-mock present in DOM
              activity|step2   MOCK_INJECTION  data-dxt-tutorial-mock present in DOM
```

Pre-existing and not caused by the hub-portal work: the same three fail with that
branch's changes stashed.

What is *not* yet established is the root cause, and the categories argue against
the obvious reading. `analyze_step` already has a `FLOATING_FALLBACK` bucket, and
`tutorial-engine.js` degrades a missing target into a floating tooltip on purpose
(`target not found/visible after polling → floating tooltip`), so a step whose
control legitimately is not present should land in that bucket, not this one.
`TARGET_MISSING` means the spotlight was active and the tooltip was *not* floating
while `_queryTarget` returned nothing — a target that existed when the step opened
and vanished before the metric read, which is a different bug from a rotted
selector. At least one of the five even documents itself as conditional ("only
visible when DX App is connected").

So this needs an instrumented run per module before anything is changed. Guessing
at a selector here risks papering over a re-render race with a hard-coded target.

`MOCK_INJECTION` is a separate defect: the tutorial injects a preview element
(`data-dxt-tutorial-mock`) to spotlight a state that only exists mid-operation, and
does not always remove it.

**Resolved 2026-08-27** (removed from the quarantine): the three dx_stream/dx_modelzoo
failures all traced to one cause — dx-runtime shipped the `yolo26-depth` family
(pipeline + `libpostprocess_yolo26depth.so` + `DxOsd::draw_depth`) and the studio's
catalog never caught up. Fixed by adding the model metadata, a depth demo, and a
filename-based `input_resolution` fallback. See `dx_stream/core/models.py`,
`dx_stream/core/demos.py`, `dx_modelzoo/core/catalog.py::_enrich_input_resolution`.

Fix the defect, then delete the matching `--deselect` line — the contract test will
confirm the entry is gone.

## Baseline (module suites, run separately)

- launcher ~521, dx_agent_dev ~228, dx_app ~410, dx_stream ~273 (excluding benchmark),
  dx_compiler ~161, dx_modelzoo ~325, dx_planner ~84, dx_benchmark ~50 (dropped from
  ~75 after `dx_benchmark/core/` was removed — the server is now a pure viewer),
  dx_monitor ~60, shared ~244, i18n_audit ~110 — all passing when run separately.
- `i18n_audit`: findings = 0 (~3400 records scanned).
- Browser 6-language + zoom audits: Playwright, via `bash scripts/run_ci.sh --browser`
  (`tests/i18n_audit/test_browser_copy_audit.py`, `tests/test_zoom_*.py`).
