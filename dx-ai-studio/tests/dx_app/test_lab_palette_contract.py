import pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]
JS = (ROOT / "dx_app" / "static" / "js" / "lab-composer.js").read_text(encoding="utf-8")
CSS = (ROOT / "dx_app" / "static" / "css" / "style.css").read_text(encoding="utf-8")

def test_palette_has_search_input():
    assert "lab-composer-model-search" in JS and "lab-composer-model-search" in CSS

def test_palette_groups_by_category():
    assert "lab-composer-model-group" in JS

def test_palette_is_scroll_capped():
    block = CSS.split("lab-composer-model-list", 1)
    assert len(block) > 1, "expected a .lab-composer-model-list rule in CSS"
    rule = block[1][:200]
    assert "max-height" in rule and "overflow" in rule

def test_palette_groups_default_expanded_not_collapsed():
    # Regression guard: groups must default OPEN on first paint (stored === undefined ->
    # expanded), and only collapse once the user explicitly toggles a header. A prior bug
    # defaulted every group to collapsed, hiding all model buttons until interaction.
    assert "stored === undefined ? true : stored" in JS

def test_palette_search_matches_category_label():
    # The visible (translated/humanized) category name must be searchable, not just the
    # raw category slug.
    seg = JS.split("function modelMatchesQuery", 1)[1][:400]
    assert "modelGroupLabel(model)" in seg
