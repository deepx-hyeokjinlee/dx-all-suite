# Testing

Tests are `pytest`, organized per module under `tests/<module>/`. Config lives in
`pytest.ini` (`testpaths = tests`) and `.coveragerc` (branch coverage over all module
source, excluding `tests/`, `.venv/`, `dx_sandbox/`).

Use the venv interpreter: `./.venv/bin/python -m pytest …`.

## Test layers

| Layer | What it covers | Needs |
|-------|----------------|-------|
| **Unit** | `core/` logic — catalog build, config, parsers, prompt wrapping, aggregation, ONNX surgery, accuracy math | nothing (stdlib) |
| **Contract** | `server.py` routes against a live in-process server on an `18xxx` test port; i18n key parity; tutorial 6-lang; shared base handler / chat engine | nothing |
| **i18n audit** | `tests/i18n_audit/` — copy inventory, missing-language, integrity, runtime lang-hook gaps, Spanish/stale-copy coverage | nothing |
| **Browser** | Playwright copy audit + language-switch matrix (optional; scripts under `scripts/`) | `playwright` install |
| **E2E** | real compile / real inference / real CLI agents | `dx_com`, dx-runtime, NPU, or CLIs |

Live-server tests bind a **`18xxx` port = `1` + the real port** (e.g. dx_app → 18080,
dx_agent_dev → 18099) so they never collide with a running studio instance.

## Running the suites

Run module suites **separately** — do not run `tests/launcher/` and
`tests/dx_agent_dev/` in a single pytest invocation (their live servers collide on the
`18xxx` range).

```bash
./.venv/bin/python -m pytest tests/launcher/ -q          # ~449 tests
./.venv/bin/python -m pytest tests/dx_agent_dev/ -q      # ~165 tests (run alone)
./.venv/bin/python -m pytest tests/dx_app/ -q
./.venv/bin/python -m pytest tests/dx_stream/ --ignore=tests/dx_stream/benchmark -q  # ~269
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

The core CI gates (see `.github/workflows/` and `scripts/`):

```bash
# 1. Module suites pass separately (see commands above).

# 2. Collection gate — must report 0 collection errors:
./.venv/bin/python -m pytest tests/ --collect-only -q \
  --ignore=tests/dx_stream/benchmark

# 3. i18n gate — static + runtime audit, then i18n_audit tests:
bash scripts/i18n_audit_gate.sh
./.venv/bin/python -m tools.i18n_audit --repo . \
  --output-json /tmp/i18n.json --output-md /tmp/i18n.md \
  --fail-on-findings --fail-on-runtime-gaps          # findings=0

# 4. Server smoke — launcher must bind and print its live banner:
./.venv/bin/python launcher/launcher.py --port 8890 --no-browser
```

Additional helper gates: `bash scripts/i18n_smoke_matrix.sh` (full i18n smoke incl.
matrix), `bash scripts/i18n_browser_audit.sh` (optional Playwright copy audit),
`bash scripts/run_ci.sh` (closed-net PR gate). Optional hardening checks:
`DX_BIND_LOCAL=1 ./launcher.sh` (loopback only) and
`DX_API_TOKEN=secret ./launcher.sh` (401 without a bearer token).

## Baseline (module suites, run separately)

- launcher ~518, dx_agent_dev ~225, dx_app ~405, dx_stream ~273 (excluding benchmark),
  dx_compiler ~144, dx_modelzoo ~325, dx_planner ~86, dx_benchmark ~75, dx_monitor ~60,
  shared ~226, i18n_audit ~100 — all passing when run separately.
- `i18n_audit`: findings = 0 (~3400 records scanned).
- Browser 6-language + zoom audits: Playwright, via `bash scripts/run_ci.sh --browser`
  (`tests/i18n_audit/test_browser_copy_audit.py`, `tests/test_zoom_*.py`).
