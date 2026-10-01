"""Guards the i18n audit fixes: category labels translate in all 6 langs (the real
"doesn't translate" cause), the broken phonetic title stub is gone, and a few unnatural
translations are corrected."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JS = ROOT / "dx_modelzoo" / "static" / "js"


def test_locallabel_falls_back_to_dict():
    # category data only ships label_en/label_ko; _localLabel must fall back to T(label_en)
    # so ja/zh/es categories translate (card + list + chips) instead of staying English.
    #
    # 한 벌만 있어야 한다. detail.js 가 폴백 없는 동명 함수를 따로 선언하고 있었고,
    # 나중에 로드되므로 이 폴백이 통째로 덮여 죽어 있었다 — 그래서 선언 위치까지
    # 함께 고정한다 (전역 충돌 자체는 tests/shared/test_static_script_scope.py 가 본다).
    src = (JS / "app.js").read_text(encoding="utf-8")
    body = src.split("function _localLabel(", 1)[1].split("function ", 1)[0]
    assert "T(en)" in body, "_localLabel must dict-fall-back via T() for missing languages"
    for other in ("catalog.js", "detail.js"):
        assert "function _localLabel(" not in (JS / other).read_text(encoding="utf-8"), (
            f"{other} 가 _localLabel 을 다시 선언하면 app.js 의 폴백이 조용히 덮인다"
        )


def test_no_broken_zoo_transliteration():
    # "DX 모델 주 탐색기" — "주" was a broken phonetic stub of "Zoo" (violates the no-
    # transliteration rule). Must be gone.
    src = (JS / "i18n-dict-catalog.js").read_text(encoding="utf-8")
    assert "DX 모델 주 탐색기" not in src
    assert "DX Model Zoo 탐색기" in src


def test_corrected_category_translations():
    src = (JS / "i18n-dict-shared.js").read_text(encoding="utf-8")
    assert "'zh-CN': '重识别'" in src        # ReID, not 重新识别 (re-recognize)
    assert "es: 'Superresolución'" in src    # one word, standard
    assert "es: 'Incrustación'" not in src   # Embedding must not be "physical inlay"


def test_accuracy_matrix_labels_localized():
    src = (JS / "detail.js").read_text(encoding="utf-8")
    assert "escapeHtml(T(label))" in src, "Accuracy-matrix row labels must go through T()"
