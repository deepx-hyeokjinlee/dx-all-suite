"""CI runner contracts — align with dx_app run_tc.sh / self-hosted gate."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

BROWSER_SUITE_PATHS = {
    "tests/i18n_audit/test_browser_copy_audit.py",
    "tests/launcher/test_sdk_library_module_nav_browser.py",
    "tests/shared/test_browser_runtime.py",
    "tests/test_iframe_lang_sync_browser.py",
    "tests/test_tutorial_e2e_journey.py",
    "tests/test_tutorial_spotlight_spot_check.py",
    "tests/test_ux_visual_gate.py",
    "tests/test_zoom_full_audit.py",
    "tests/test_zoom_layout_contracts.py",
    "tests/test_zoom_modal_audit.py",
}


def test_run_ci_script_exists_and_executable():
    script = ROOT / "scripts" / "run_ci.sh"
    assert script.is_file()
    text = script.read_text(encoding="utf-8")
    assert "tests/launcher/" in text
    assert "tests/dx_agent_dev/" in text
    assert "i18n_audit_gate.sh" in text


def test_release_ver_matches_studio_version_ssot():
    release_ver = (ROOT / "release.ver").read_text(encoding="utf-8").strip()
    studio_js = (ROOT / "shared" / "static" / "studio-version.js").read_text(encoding="utf-8")
    assert release_ver.startswith("v")
    semver = release_ver.lstrip("v")
    assert f"semver: '{semver}'" in studio_js


def test_ci_workflow_uses_self_hosted_runner():
    workflow = (
        ROOT.parent / ".github" / "workflows" / "dx-ai-studio-pytest.yml"
    ).read_text(encoding="utf-8")
    assert "self-hosted" in workflow
    assert "run_ci.sh" in workflow
    assert "ubuntu-latest" not in workflow
    assert "ci-browser-smoke" not in workflow


def test_i18n_smoke_workflow_is_manual_dispatch_only():
    workflow = (
        ROOT.parent / ".github" / "workflows" / "dx-ai-studio-i18n-audit.yml"
    ).read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow
    assert "pull_request:" not in workflow


def test_run_ci_excludes_browser_tests_from_default_gate():
    script = (ROOT / "scripts" / "run_ci.sh").read_text(encoding="utf-8")
    assert "BROWSER_TESTS=(" in script
    missing = sorted(path for path in BROWSER_SUITE_PATHS if path not in script)
    assert not missing, f"Browser suite inventory is incomplete: {missing}"
    assert '"${IGNORE_BROWSER[@]}"' in script
    assert 'RUN_BROWSER=1' in script or "--browser" in script


def test_run_ci_prefilters_explicit_root_browser_paths():
    script = (ROOT / "scripts" / "run_ci.sh").read_text(encoding="utf-8")
    stage_five = script.split('== 5/7 Module + shared + root contract suites (no browser) ==', 1)[1]

    assert "ROOT_TESTS=()" in script
    assert "for _root_test in tests/test_*.py; do" in script
    assert 'if [[ "$_root_test" == "$_bt" ]]; then' in script
    assert '"${ROOT_TESTS[@]}"' in stage_five
    assert "tests/test_*.py" not in stage_five


def test_run_ci_runs_browser_suites_in_isolated_pytest_processes():
    script = (ROOT / "scripts" / "run_ci.sh").read_text(encoding="utf-8")
    assert 'for _bt in "${BROWSER_TESTS[@]}"; do' in script
    assert '"$PY" -m pytest "$_bt" -q --tb=short' in script


def test_i18n_browser_audit_uses_test_interpreter_without_forced_browser_download():
    script = (ROOT / "scripts" / "i18n_browser_audit.sh").read_text(encoding="utf-8")
    assert '"$VENV_PYTHON" -c "import playwright"' in script
    assert "playwright install chromium" not in script


def test_ci_dependency_manifest_covers_collection_dependencies():
    manifest = ROOT / "requirements-ci.txt"
    assert manifest.is_file()

    package_names = {
        line.split(";", 1)[0].split("[", 1)[0]
        .split("<", 1)[0].split(">", 1)[0].split("=", 1)[0]
        .strip().lower()
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert {
        "pytest", "numpy", "onnx", "pillow", "playwright", "jinja2", "cffi"
    } <= package_names


def test_run_ci_runs_inference_e2e_gate_isolated():
    """The inference triple gate blocks merges and MUST run in its own process.

    tests/e2e/conftest.py rebinds DX_APP_ROOT at import time and dx_app.core.config
    freezes its paths on first import, so sharing a pytest process with the module
    suites would pin the wrong tree for one of them.
    """
    script = (ROOT / "scripts" / "run_ci.sh").read_text(encoding="utf-8")
    assert '"$PY" -m pytest tests/e2e/ -q --tb=short -m e2e_mock' in script, (
        "run_ci.sh must run the e2e_mock tier as a blocking stage"
    )
    stage = script.split("== 6/7 Inference E2E triple gate", 1)
    assert len(stage) == 2, "the inference E2E gate must be a numbered stage"
    # It must NOT be inside the optional --browser / --coverage / --ux blocks.
    assert script.index("== 6/7 Inference E2E triple gate") < script.index(
        'if [ "$RUN_COVERAGE" = "1" ]; then'
    ), "the inference E2E gate must be blocking, not an opt-in extra"


def test_run_ci_excludes_e2e_from_shared_process_stages():
    """The collection gate and the module stage must not import tests/e2e."""
    script = (ROOT / "scripts" / "run_ci.sh").read_text(encoding="utf-8")
    collection = script.split("== 1/7 Collection gate ==", 1)[1].split("== 2/7", 1)[0]
    module_stage = script.split("== 5/7 Module", 1)[1].split("== 6/7", 1)[0]
    for name, chunk in (("collection gate", collection), ("module stage", module_stage)):
        assert "--ignore=tests/e2e" in chunk, (
            f"{name} must --ignore=tests/e2e (its conftest rebinds DX_APP_ROOT)"
        )


# Pre-existing failures deselected from the blocking gate. This list is a debt
# ledger: it may SHRINK, never grow. Adding an entry means a new regression was
# waved through, which is exactly what the gate exists to prevent.
QUARANTINED = {
    "tests/dx_modelzoo/test_legal_enrich.py::test_all_models_have_complete_legal_block",
    "tests/test_shared_css_foundation.py::test_dx_app_css_no_longer_defines_shared_foundation",
}


def _quarantined_in_script() -> set:
    script = (ROOT / "scripts" / "run_ci.sh").read_text(encoding="utf-8")
    block = script.split("QUARANTINE=(", 1)[1].split(")", 1)[0]
    return {
        ln.strip().removeprefix("--deselect").strip()
        for ln in block.splitlines()
        if ln.strip().startswith("--deselect")
    }


def test_quarantine_list_never_grows():
    """The gate's deselect list is a debt ledger — it may shrink, never grow."""
    actual = _quarantined_in_script()
    added = actual - QUARANTINED
    assert not added, (
        "New entries added to the run_ci.sh quarantine — a regression was waved "
        f"through the blocking gate: {sorted(added)}"
    )


def test_quarantine_entries_are_documented():
    """Every quarantined test must be listed in docs/testing.md with a reason."""
    actual = _quarantined_in_script()
    doc = (ROOT / "docs" / "testing.md").read_text(encoding="utf-8")
    undocumented = sorted(n for n in actual if n.split("::")[-1] not in doc)
    assert not undocumented, (
        "Quarantined tests missing from docs/testing.md: " + str(undocumented)
    )


def test_quarantined_tests_still_exist():
    """A quarantined node id that no longer resolves is stale — drop it from the list."""
    for node in _quarantined_in_script():
        path = ROOT / node.split("::", 1)[0]
        assert path.is_file(), f"quarantined test file is gone, remove it: {node}"
        func = node.split("::")[-1]
        assert f"def {func}(" in path.read_text(encoding="utf-8"), (
            f"quarantined test no longer exists, remove it from run_ci.sh: {node}"
        )


def _coveragerc_sources() -> set:
    """Module names declared under [run] source in .coveragerc."""
    text = (ROOT / ".coveragerc").read_text(encoding="utf-8")
    body = text.split("source", 1)[1].split("omit", 1)[0]
    return {
        ln.strip()
        for ln in body.splitlines()
        if ln.strip() and not ln.strip().startswith(("=", "[", "#"))
    }


def test_coverage_stanza_measures_every_declared_source():
    """--coverage must measure all ten .coveragerc sources, not just two.

    Regression guard: the stanza used to pass only --cov=shared --cov=launcher
    while .coveragerc declared ten sources, so eight well-tested modules reported
    as uncovered and the number was meaningless.
    """
    script = (ROOT / "scripts" / "run_ci.sh").read_text(encoding="utf-8")
    block = script.split("COV_ARGS=(", 1)[1].split(")", 1)[0]
    measured = {tok.split("=", 1)[1] for tok in block.split() if tok.startswith("--cov=")}
    declared = _coveragerc_sources()
    missing = sorted(declared - measured)
    assert not missing, f"declared in .coveragerc but never measured: {missing}"


def test_coverage_uses_append_across_isolated_processes():
    """launcher/dx_agent_dev/e2e cannot share a pytest process, so coverage must append."""
    script = (ROOT / "scripts" / "run_ci.sh").read_text(encoding="utf-8")
    cov_block = script.split("== Optional: Python coverage", 1)[1]
    assert cov_block.count("--cov-append") >= 3, (
        "each isolated coverage run after the first must --cov-append, "
        "otherwise it overwrites the previous run's data"
    )
    assert "scripts/coverage_gate.py" in cov_block, (
        "coverage must be compared against config/coverage_baseline.json"
    )


def test_browser_suites_support_sharding():
    script = (ROOT / "scripts" / "run_ci.sh").read_text(encoding="utf-8")
    assert "--shard=*)" in script, "run_ci.sh must accept --shard=i/N"
    assert "SHARD_TOTAL" in script and "_shard_suites" in script
    # The i18n copy audit is indivisible — it must not run once per shard.
    assert 'if [ "$SHARD_INDEX" = "1" ]; then' in script, (
        "the i18n browser audit must be pinned to one shard"
    )


def test_cross_browser_and_coverage_jobs_are_advisory():
    """Staged rollout: only the run_ci.sh gate blocks a merge for now."""
    workflow = (
        ROOT.parent / ".github" / "workflows" / "dx-ai-studio-pytest.yml"
    ).read_text(encoding="utf-8")
    for job in ("cross-browser:", "coverage:"):
        assert job in workflow, f"{job} job missing from the PR workflow"
    assert workflow.count("continue-on-error: true") == 2, (
        "exactly the two advisory jobs (cross-browser, coverage) may be "
        "continue-on-error — the pytest gate must block"
    )
    assert "DX_BROWSER_ENGINES: chromium,firefox" in workflow
    assert "playwright-traces-shard-" in workflow, (
        "failure traces must be uploaded as artifacts (Trace Viewer)"
    )
