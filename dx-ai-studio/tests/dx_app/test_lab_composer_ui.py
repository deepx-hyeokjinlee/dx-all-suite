"""RED static contracts for the DOM-safe progressive Lab Composer UI."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "dx_app" / "templates" / "index.html"
COMPOSER_JS = ROOT / "dx_app" / "static" / "js" / "lab-composer.js"
LAB_PORTAL_JS = ROOT / "dx_app" / "static" / "js" / "lab-portal.js"
I18N_JS = ROOT / "dx_app" / "static" / "js" / "i18n.js"
COMPOSER_I18N_KEYS = {
    "Quick Start",
    "Templates",
    "Customize",
    "Undo",
    "Redo",
    "Save Output",
    "Select input asset",
    "Device ID",
    "Device ID must be a non-negative integer",
    "Plugin palette",
    "Drag a custom plugin to Preprocess or Postprocess",
    "Custom plugin",
    "Save Recipe",
    "Export Recipe",
    "Import Recipe",
    "Run Package",
    "Developer Package",
    "Reusable Recipe",
    "Export Preflight",
    "Recipe saved",
    "Recipe import failed",
    "Recipe export failed",
    "Choose a recipe JSON file",
    "Copy-out verified",
    "Plugins",
    "Validation",
    "Add custom preprocess",
    "Add custom postprocess",
    "Apply Plugin Scaffold",
    "Run Workflow",
    "Export Package",
    "Workflow validation blocked",
}
LOCALES = ("ko", "ja", "zh-CN", "zh-TW", "es")

COMPOSER_ROUTES = (
    "/api/lab/composer/quick_start",
    "/api/lab/composer/template",
    "/api/lab/composer/customize",
    "/api/lab/composer/plugin/dry_run",
    "/api/lab/composer/plugin/apply",
    "/api/lab/composer/run",
    "/api/lab/composer/recipe/export",
    "/api/lab/composer/recipe/import",
    "/api/lab/composer/export",
)


def _composer_source():
    return COMPOSER_JS.read_text(encoding="utf-8")


def test_lab_has_composer_card_with_quick_start_and_templates():
    html = INDEX.read_text(encoding="utf-8")
    source = _composer_source()

    assert 'data-lab-flow="composer"' in html
    assert "Quick Start" in source
    assert "Templates" in source


def test_lab_opens_composer_first_with_builder_regions():
    html = INDEX.read_text(encoding="utf-8")
    portal = LAB_PORTAL_JS.read_text(encoding="utf-8")
    source = _composer_source()

    assert html.index('id="lab-card-composer"') < html.index('id="lab-card-add-model"')
    assert "function _openComposerByDefault" in portal
    assert "await _openComposerByDefault();" in portal
    for name in ("ComposerState", "ComposerApi", "ComposerRenderer"):
        assert name in source
    for region in (
        "lab-composer-palette",
        "lab-composer-canvas",
        "lab-composer-inspector",
    ):
        assert region in source


def test_customize_is_progressive_after_initial_workflow_exists():
    source = _composer_source()

    assert "Customize" in source
    assert "currentWorkflow" in source
    assert "if (!currentWorkflow)" in source
    for node_name in ("Input", "Preprocess", "Inference", "Postprocess", "Visualize"):
        assert node_name in source


def test_workflow_preview_exposes_server_resolved_model_and_input():
    source = _composer_source()

    assert "function renderWorkflowSummary" in source
    assert "workflow.model" in source
    assert "workflow.input" in source


def test_graph_is_hidden_until_a_workflow_is_created():
    source = _composer_source()

    assert 'graph.hidden = !currentWorkflow' in source
    assert 'graph.setAttribute("aria-hidden", String(!currentWorkflow))' in source


def test_blocked_validation_disables_run_and_export_controls():
    source = _composer_source()

    assert 'validation.status !== "ready"' in source
    assert "runButton.disabled = blocked" in source
    assert "exportButton.disabled = blocked" in source


def test_run_posts_only_the_server_issued_manifest_id():
    source = _composer_source()

    assert '"/api/lab/composer/run"' in source
    assert re.search(
        r'await request\(\s*"/api/lab/composer/run",\s*\{\s*'
        r"manifest_id: currentWorkflow\.manifest_id\s*}\s*\)",
        source,
    )
    assert "JSON.parse(runPayload)" not in source
    assert "JSON.stringify({ workflow:" not in source


def test_composer_distinguishes_model_load_errors_and_safe_package_downloads():
    source = _composer_source()

    assert "modelLoadError = true" in source
    assert "safeOutputUrl(result.download.url)" in source


def test_customize_uses_server_validated_patches_and_confirmed_plugin_scaffolds():
    source = _composer_source()

    assert "function applyCustomization" in source
    assert "function applyPluginScaffold" in source
    assert "customizationHistory" in source
    assert "Undo" in source
    assert "Redo" in source
    assert '"/api/lab/composer/customize"' in source
    assert "'/api/lab/composer/plugin/dry_run'" in source
    assert "'/api/lab/composer/plugin/apply'" in source
    assert "workflow: currentWorkflow.workflow" not in source


def test_customize_graph_cards_show_status_parameters_and_plugin_actions():
    source = _composer_source()

    assert "lab-composer-node-status" in source
    assert "lab-composer-node-params" in source
    assert "Add custom preprocess" in source
    assert "Add custom postprocess" in source
    assert "save_output" in source


def test_customize_supports_server_validated_model_asset_and_plugin_drag_actions():
    source = _composer_source()

    assert "model_selection" in source
    assert "input_selection" in source
    assert "loadCompatibleAssets" in source
    assert "dragstart" in source
    assert "dragover" in source
    assert "drop" in source
    assert "planPluginScaffold(stage, language)" in source


def test_recipe_and_export_controls_use_server_validated_workflow_operations():
    source = _composer_source()

    assert "function saveRecipe" in source
    assert "function exportRecipe" in source
    assert "function importRecipe" in source
    assert "function renderRecipeControls" in source
    assert "function renderExportPanel" in source
    assert "FileReader" in source
    assert "'/api/lab/composer/recipe/export'" in source
    assert "'/api/lab/composer/recipe/import'" in source
    assert "package_type: packageType" in source
    assert "manifest_id: currentWorkflow.manifest_id" in source
    assert "recipe: recipe" in source
    assert "workflow: currentWorkflow.workflow" not in source


def test_recipe_download_defers_blob_url_cleanup_until_after_click():
    source = _composer_source()

    assert "function downloadRecipe" in source
    assert "link.click();" in source
    assert "setTimeout(function () { URL.revokeObjectURL(url); }, 0);" in source


def test_recipe_import_and_package_download_validate_response_shapes():
    source = _composer_source()

    assert "recipe === null || Array.isArray(recipe)" in source
    assert "typeof result.download.name !== 'string'" in source


def test_composer_uses_dom_apis_and_text_content_without_inner_html():
    source = _composer_source()

    assert "document.createElement" in source
    assert ".textContent" in source
    assert "innerHTML" not in source


def test_composer_ui_names_every_server_composer_route():
    source = _composer_source()

    for route in COMPOSER_ROUTES:
        assert route in source


def test_all_composer_strings_have_six_locale_coverage():
    source = _composer_source()
    translations = I18N_JS.read_text(encoding="utf-8")

    for key in COMPOSER_I18N_KEYS:
        assert f"T('{key}')" in source
        match = re.search(
            rf"'{re.escape(key)}':\s*\{{(.*?)\n\s*\}}\s*(?:,|\n)",
            translations,
            re.S,
        )
        assert match, key
        entry = match.group(1)
        assert all(f"{locale}:" in entry or f"'{locale}':" in entry for locale in LOCALES), key


def test_package_type_choices_have_localized_non_english_labels():
    translations = I18N_JS.read_text(encoding="utf-8")

    for key in ("Run Package", "Developer Package", "Reusable Recipe"):
        match = re.search(
            rf"'{re.escape(key)}':\s*\{{(.*?)\n\s*\}}\s*(?:,|\n)",
            translations,
            re.S,
        )
        assert match, key
        entry = match.group(1)
        for locale in ("ko", "ja", "zh-CN", "zh-TW"):
            localized = re.search(rf"'?{re.escape(locale)}'?\s*:\s*'([^']+)'", entry)
            assert localized, f"{key}: {locale}"
            assert localized.group(1) != key, f"{key}: {locale}"