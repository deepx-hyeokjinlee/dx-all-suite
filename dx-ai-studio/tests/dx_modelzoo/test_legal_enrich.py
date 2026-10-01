"""Legal fields the ModelZoo source omits but which are mechanically derivable
(copyright = source repo owner, license body = canonical SPDX text) must be filled,
without overwriting curated values. Every model should end up with a complete legal block.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "dx_modelzoo"))


def _models():
    from core import catalog as C
    return C.get_catalog()["models"]


def _no_reference_ids():
    import json
    gen = json.loads((REPO_ROOT / "dx_modelzoo" / "data" / "generated_catalog.json").read_text(encoding="utf-8"))
    return {g["id"] for g in gen["models"]
            if str(((g.get("legal") or {}).get("source_url") or "")).strip().lower() in ("no reference", "-")}


def test_no_reference_is_never_shown_as_a_source():
    """page 가 출처를 "No Reference" 로 적은 model 은 publish_only 든 conf row 든 출처를 비운다 — 그 글자를
    URL 자리에 두지 않는다 (per-model dx_app 에서 conf row 가 된 28 개가 그랬다, 2026-10-01)."""
    from core import catalog as C
    m = {"legal": {"source_url": "No Reference", "license": "Apache-2.0"}}
    C._enrich_legal(m)
    assert m["legal"]["source_url"] == "" and m["legal"]["license_text"]
    shown = [x["id"] for x in _models() if str((x.get("legal") or {}).get("source_url") or "").lower() == "no reference"]
    assert not shown, shown[:10]


def test_all_models_have_complete_legal_block():
    ms = _models()
    # source_url + copyright are mechanically derivable for every model: the source
    # comes from the studio's curated catalog or the staging dx-modelzoo model YAML
    # `reference` field, and copyright is derived from the repo owner.
    # publish page 에만 있는 model (publish_only) 중 page 가 출처를 "No Reference" 로 적은 것은 비워 둔다 — 지어내지
    # 않는다 (spec 2026-10-01 dx_app per-model layout 결정 8).
    # per-model dx_app 에서는 그런 model 도 conf 에 있어 publish_only 가 아니다 — page 의 말 ("No Reference") 로 가린다.
    no_ref = _no_reference_ids()
    for key in ("source_url", "copyright"):
        missing = [m["id"] for m in ms if not (m.get("legal") or {}).get(key)
                   and not (m["id"] in no_ref and not (m.get("legal") or {}).get("source_url"))]
        assert not missing, f"{key} missing for: {missing[:10]}"
    # License is filled wherever the upstream license is known (curated, or mapped from
    # the source repo). It must always come paired with its canonical license_text — we
    # never assert one without the other. Models whose upstream declares no discoverable
    # license are honestly left blank rather than assigned a fabricated license.
    for m in ms:
        lg = m.get("legal") or {}
        if lg.get("license"):
            assert lg.get("license_text"), f"license without canonical text: {m['id']}"
        if lg.get("license_text"):
            assert lg.get("license"), f"license_text without license: {m['id']}"


def test_copyright_derived_from_source_repo_owner():
    ms = {m["id"]: m for m in _models()}
    assert ms["levit384"]["legal"]["copyright"] == "Facebook"             # huggingface.co/facebook
    assert ms["yolov7_w6"]["legal"]["copyright"] == "WongKinYiu"          # curated, preserved
    assert ms["realesrgan_x2"]["legal"]["copyright"] == "xinntao"         # github owner, verbatim


def test_license_text_is_canonical_reference():
    ms = {m["id"]: m for m in _models()}
    # efficientformerv2_l is Apache-2.0 (snap-research/EfficientFormer); yolov7_w6 is GPL-3.0.
    assert "apache.org/licenses/LICENSE-2.0" in ms["efficientformerv2_l"]["legal"]["license_text"]
    assert "gpl-3.0" in ms["yolov7_w6"]["legal"]["license_text"]


# yolo26_depth 계열은 2026-09 에 공개 ModelZoo 에 추가됐다. 그전까지 studio 카탈로그는
# 이 다섯 개를 legal 없이 내보냈고, 게이트는 "상류에 데이터가 없다" 는 잘못된 근거로
# deselect 되어 있었다. 실제로는 (1) generated_catalog.json 이 추가 이전 산출물이었고
# (2) studio id `yolo26_depth_n` 이 생성 id `yolo26_depth_n_768x768` 과 매칭되지 않았다.
#
# test_all_models_have_complete_legal_block 은 "비어 있지 않다" 만 본다. 다음 동기화가
# 값을 비우거나 엉뚱한 저장소를 가리켜도 그 테스트는 통과하므로, 실제 값을 여기 고정한다.
# id 는 publish page 의 .dxnn 이름 (yolo26-depth-n_768x768) — main 과 per-model dx_app 이 같은 id 를 쓰게
# (spec 2026-10-01 dx_app per-model layout). 예전 id 는 yolo26_depth_n 이었다.
_YOLO26_DEPTH_IDS = (
    "yolo26_depth_n_768x768",
    "yolo26_depth_s_768x768",
    "yolo26_depth_m_768x768",
    "yolo26_depth_l_768x768",
    "yolo26_depth_x_768x768",
)


def test_yolo26_depth_carries_its_upstream_legal():
    by_id = {m["id"]: m for m in _models()}
    for mid in _YOLO26_DEPTH_IDS:
        assert mid in by_id, f"{mid} 가 카탈로그에서 사라졌다"
        lg = by_id[mid].get("legal") or {}
        assert lg.get("source_url") == "https://github.com/ultralytics/ultralytics", (
            f"{mid}: source_url={lg.get('source_url')!r}"
        )
        assert lg.get("license") == "AGPL-3.0", f"{mid}: license={lg.get('license')!r}"
        # 고치기 전에는 license 를 몰라 fallback 인 "restricted" 가 붙어 있었다.
        # 이제 AGPL 로 판별되므로 _LICENSE_COMMERCIAL 의 "copyleft" 가 되어야 한다 —
        # 같은 "쓰기 조심" 이라도 이유가 다르고, UI 가 그 이유를 표시한다.
        assert lg.get("commercial_use") == "copyleft", (
            f"{mid}: commercial_use={lg.get('commercial_use')!r}"
        )
        assert lg.get("copyright"), f"{mid}: copyright 가 저장소 소유자에서 파생되지 않았다"
