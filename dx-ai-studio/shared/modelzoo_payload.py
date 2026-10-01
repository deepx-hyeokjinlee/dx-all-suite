"""공개 DEEPX Model Zoo(developer.deepx.ai/modelzoo) 리더.

예전 이 파일은 서버 렌더 HTML 테이블(3행 그룹 헤더)을 파싱했다. 페이지가
리팩토링되면서 그 테이블은 사라지고, 문서 안에 구조화된 페이로드가 실린다:

    window.__MODEL_ZOO_DATA__ = {
      fields: [task, name, display, dataset, input, ops, params, license,
               metric, source, rawAcc, onnx, qlAcc, qlDxnn, qlJson,
               qpAcc, qpDxnn, qpJson, qmAcc, qmDxnn, qmJson, fps, fpsw],
      base:   "https://sdk.deepx.ai/modelzoo/",
      rows:   [[...], ...]
    }

공식 JSON 엔드포인트는 없다 — 실측으로 확인했다(페이지 네트워크 요청 6건,
XHR/fetch 0건, /modelzoo/*.json 404, /api/modelzoo 는 페이지로 301, 버킷 목록 403).
그래서 이건 여전히 스크래핑이지만, 대상이 HTML 테이블에서 인라인 JSON 으로
바뀐 것이고 그쪽이 훨씬 튼튼하다: `fields` 가 열 이름을 주므로 위치에 기대지
않는다. 이 저장소는 위치 기반 파싱 탓에 카탈로그 캐시의 필드가 한 칸씩 밀려
(`fps` ← `fps_per_watt`) 잘못된 성능 수치를 내보낸 전례가 있다.

공식 계약이 아니므로 **조용히 실패하지 않는다.** 전역이 없거나 필수 열이
사라지면 부분 카탈로그를 만드는 대신 예외를 던진다.
"""
from __future__ import annotations

import json
from typing import Any

_GLOBAL = "window.__MODEL_ZOO_DATA__"

# 없으면 읽을 수 없는 열. (qm* 처럼 희소한 것은 필수가 아니다.)
_REQUIRED_FIELDS = (
    "task", "name", "display", "dataset", "input", "ops", "params",
    "license", "metric", "source", "rawAcc", "onnx",
    "qlAcc", "qlDxnn", "qlJson", "fps", "fpsw",
)

# 페이로드의 열 이름 → 우리가 쓰는 아티팩트 이름
_ARTIFACTS = {
    "onnx": "onnx",
    "qlDxnn": "qlite_dxnn", "qlJson": "qlite_json",
    "qpDxnn": "qpro_dxnn",  "qpJson": "qpro_json",
    "qmDxnn": "qmaster_dxnn", "qmJson": "qmaster_json",
}
_ACCURACY = {"rawAcc": "raw", "qlAcc": "qlite", "qpAcc": "qpro", "qmAcc": "qmaster"}


def _extract_payload(html: str) -> dict[str, Any]:
    """전역 대입문에서 객체를 꺼낸다.

    끝은 **괄호 균형**으로 찾는다. 정규식으로 첫 `}` 를 잡으면 중첩 객체에서
    잘리고, 그러면 절반짜리 JSON 을 파싱하려다 엉뚱한 곳에서 터진다.
    """
    at = html.find(_GLOBAL)
    if at < 0:
        raise ValueError(
            f"{_GLOBAL} 을 찾을 수 없다 — 페이지 구조가 또 바뀌었거나 응답이 "
            "우리가 기대한 문서가 아니다. 부분 카탈로그를 만들지 않는다."
        )
    start = html.find("{", at)
    if start < 0:
        raise ValueError(f"{_GLOBAL} 뒤에 객체가 없다")
    depth = 0
    for end in range(start, len(html)):
        ch = html[end]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(html[start:end + 1])
    raise ValueError(f"{_GLOBAL} 의 객체가 닫히지 않았다")


def _as_number(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_public_payload(html: str) -> list[dict[str, Any]]:
    """페이지 HTML → 모델 행 목록."""
    payload = _extract_payload(html)
    fields = payload.get("fields")
    rows = payload.get("rows")
    if not isinstance(fields, list) or not isinstance(rows, list):
        raise ValueError(f"{_GLOBAL} 에 fields/rows 가 없다")

    missing = [f for f in _REQUIRED_FIELDS if f not in fields]
    if missing:
        raise ValueError(
            f"fields 에서 필수 열이 사라졌다: {missing} — 이름으로 읽으므로 "
            "열이 바뀌면 값이 밀리는 대신 여기서 멈춘다."
        )
    at = {name: i for i, name in enumerate(fields)}
    base = (payload.get("base") or "").rstrip("/") + "/"

    def cell(row, name):
        i = at.get(name)
        return row[i] if i is not None and i < len(row) else None

    out: list[dict[str, Any]] = []
    for row in rows:
        artifacts = {}
        for field, key in _ARTIFACTS.items():
            raw = cell(row, field)
            if raw:
                # 페이로드의 상대경로는 `~onnx/...` 꼴이다.
                artifacts[key] = base + str(raw).lstrip("~/")
        out.append({
            "task": cell(row, "task"),
            "name": cell(row, "name"),
            "display": cell(row, "display"),
            "dataset": cell(row, "dataset"),
            "input": cell(row, "input"),
            "ops": _as_number(cell(row, "ops")),
            "params": _as_number(cell(row, "params")),
            "license": cell(row, "license"),
            "metric": cell(row, "metric"),
            "source": cell(row, "source"),
            "fps": _as_number(cell(row, "fps")),
            "fps_per_watt": _as_number(cell(row, "fpsw")),
            "accuracy": {tier: _as_number(cell(row, field))
                         for field, tier in _ACCURACY.items()},
            "artifacts": artifacts,
        })
    return out


# ── 어댑터 인터페이스 ────────────────────────────────────────
# 어댑터와 studio_id_map 은 {모델id: {leaf 경로: 값}} 을 기대한다. leaf 경로는
# 예전 HTML 파서가 쓰던 것과 같다 — 스키마는 이미 specification.dataset /
# parameters / metric.name / evaluation.qmaster 를 정의해 두고 있었고, 채우는
# 쪽이 없었을 뿐이다. 그래서 흡수는 새 경로를 만드는 일이 아니라 비어 있던
# 자리를 채우는 일이다.

_LEAF_OF = {
    "display":      "display.class_name",
    "dataset":      "specification.dataset",
    "input":        "specification.input_resolution",
    "ops":          "specification.operations",
    "params":       "specification.parameters",
    "license":      "legal.license",
    "metric":       "specification.metric.name",
    "source":       "legal.source_url",
    "fps":          "performance.fps",
    "fps_per_watt": "performance.fps_per_watt",
}
_ACCURACY_LEAF = {
    "raw": "evaluation.raw.accuracy", "qlite": "evaluation.qlite.accuracy",
    "qpro": "evaluation.qpro.accuracy", "qmaster": "evaluation.qmaster.accuracy",
}


def _artifact_model_id(artifacts: dict) -> str:
    """아티팩트 파일명에서 모델 id 를 만든다.

    canonical_model_id 에 **전체 파일명**을 넘긴다. 미리 확장자를 떼고 넘기면
    두 번 깎여서 숫자 안에 점이 있는 이름이 망가진다
    (`...mobilnet0.5_120x120.dxnn` → `...mobilnet0`).
    """
    from dx_modelzoo.metadata.normalization import canonical_model_id

    for key in ("qlite_dxnn", "qpro_dxnn", "onnx"):
        url = artifacts.get(key)
        if url:
            return canonical_model_id(url.rstrip("/").split("/")[-1])
    return ""


def parse_public_modelzoo_html(html: str) -> tuple[dict, list[str]]:
    """공개 페이지 HTML → (모델 dict, 경고 목록)."""
    warnings: list[str] = []
    models: dict[str, dict] = {}

    for row in parse_public_payload(html):
        fields: dict = {}
        for src, leaf in _LEAF_OF.items():
            value = row.get(src)
            if value not in (None, ""):
                fields[leaf] = value
        for tier, leaf in _ACCURACY_LEAF.items():
            value = row["accuracy"].get(tier)
            # 없는 값은 키를 만들지 않는다. merge 는 '값이 있는 소스' 를 고르므로
            # None 을 넣으면 다른 소스가 채운 값을 빈 값으로 덮어쓸 수 있다.
            if value is not None:
                fields[leaf] = value
        for key, url in row["artifacts"].items():
            fields[f"artifacts.{key}.remote_url"] = url

        mid = _artifact_model_id(row["artifacts"])
        if not mid:
            from dx_modelzoo.metadata.normalization import canonical_model_id
            mid = canonical_model_id(row.get("name") or row.get("display") or "")
        if not mid:
            warnings.append(f"모델 id 를 만들 수 없는 행: {row.get('display')!r}")
            continue
        if mid in models:
            models[mid].update(fields)
        else:
            models[mid] = fields
    return models, warnings
