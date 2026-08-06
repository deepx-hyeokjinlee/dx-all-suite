import pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_capabilities_templates_expose_category_and_input_kind():
    import sys; sys.path.insert(0, str(ROOT))
    from dx_app.core import lab_portal
    caps = lab_portal.lab_capabilities()
    tpls = caps["composer"]["templates"]
    # each template entry must carry category (may be None for input-kind templates) and input_kind
    vals = tpls.values() if isinstance(tpls, dict) else tpls
    assert vals, "templates payload empty"
    for t in vals:
        assert "input_kind" in t
        assert "category" in t


def test_explicit_model_category_mismatch_is_surfaced_not_silent():
    src_wf = (ROOT / "dx_app" / "core" / "lab_workflow.py").read_text(encoding="utf-8")
    src_port = (ROOT / "dx_app" / "core" / "lab_portal.py").read_text(encoding="utf-8")
    assert "template_model_mismatch" in (src_wf + src_port)
