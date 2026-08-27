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

Run the real-NPU tier with:

```bash
DX_E2E_NPU_MODEL=<model> ./.venv/bin/python -m pytest tests/e2e/ -m e2e_npu -q
```

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

Measures **all ten** `.coveragerc` sources (it used to measure only `shared` + `launcher`,
which made eight well-tested modules look uncovered). The suites cannot share one pytest
process — launcher and dx_agent_dev collide on the `18xxx` ports and `tests/e2e` rebinds
`DX_APP_ROOT` — so it runs four groups with `--cov-append` and reports once.

`scripts/coverage_gate.py` then compares against `config/coverage_baseline.json`
(0.5%p tolerance). Report-only during the staged rollout; set `DX_COVERAGE_ENFORCE=1`
to make a drop fail. Refresh the baseline with `python scripts/coverage_gate.py --update`.

Baseline (`config/coverage_baseline.json`, branch coverage over 20,346 statements):

| module | cover | | module | cover |
|---|---|---|---|---|
| dx_planner | 91.7% | | shared | 74.8% |
| dx_benchmark | 91.2% | | launcher | 70.7% |
| dx_monitor | 85.0% | | dx_app | 66.7% |
| dx_modelzoo | 83.8% | | dx_stream | 65.0% |
| dx_agent_dev | 79.9% | | dx_compiler | 57.6% |

`dx_compiler` and `dx_stream` remain the thinnest. The largest remaining gaps are
the two module servers (`dx_stream/server.py` 45%, `dx_compiler/server.py` 36%) and
`compiler_service.py` (55%) — route-level contract tests against a live `18xxx`
server, the pattern the rest of the repo already uses, are the natural next step.

Additional helper/manual checks, not part of `run_ci.sh`:

- `bash scripts/i18n_smoke_matrix.sh` — full i18n smoke incl. matrix.
- `bash scripts/i18n_browser_audit.sh` — optional Playwright copy audit.
- Server smoke (manual, not gated by `run_ci.sh`): confirm the launcher binds and
  prints its live banner — `./.venv/bin/python launcher/launcher.py --port 8890
  --no-browser`.
- Hardening checks: `DX_BIND_LOCAL=1 ./launcher.sh` (loopback only) and
  `DX_API_TOKEN=secret ./launcher.sh` (401 without a bearer token).

## Quarantined pre-existing failures

Stage 5/7 deselects two tests that were **already failing before the PR gate existed**.
They are real content defects, not environment gaps, so they are NOT papered over with
skip guards — they are deselected in `scripts/run_ci.sh` (`QUARANTINE=(...)`) where they
stay visible and counted.

`tests/shared/test_ci_contracts.py` enforces three things: the list may only **shrink**,
every entry must be documented here, and a stale entry (test deleted/renamed) fails the
gate. So the debt cannot quietly grow.

| Test | Defect | Needs |
|------|--------|-------|
| `test_all_models_have_complete_legal_block` | The `yolo26-depth-*` family reaches the catalog from the dx_app source tree, not the ModelZoo sync snapshot, so it carries only `commercial_use: restricted` and no full legal block. | Upstream licence data. **Do not fabricate** — a wrong licence claim is worse than a missing one. |
| `test_dx_app_css_no_longer_defines_shared_foundation` | `dx_app` CSS re-defines shared-foundation rules (`:focus-visible`). | Design call: move the rules back to `shared/`, or update the contract. |

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
