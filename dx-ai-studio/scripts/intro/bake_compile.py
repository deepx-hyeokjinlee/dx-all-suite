"""intro 의 Compiler 장면을 굽는다 — Ultralytics 공식 YOLO26n 의 실제 ONNX graph.

spec: docs/superpowers/specs/2026-09-30-intro-app-compiler-scenes-design.md

node 하나가 화면의 점 하나, 연결 하나가 선 하나다. 가로는 입력에서의 깊이 (최장 경로), 세로는 힘으로
푼다 (layout 의 주석). 지어낸 network 가 아니라 이 model 의 진짜 연결이다.

    .venv/bin/python scripts/intro/bake_compile.py --onnx <yolo26n.onnx> --dxnn <yolo26-n_640x640.dxnn> \\
        [--fps 212.21]

`--fps` 는 공식 `.dxnn` 을 DX-M1 에서 잰 값 (`run_model -b`) — 이 script 는 NPU 가 없어도 돈다.
"""
from __future__ import annotations

import argparse
import datetime
import json
from collections import Counter
from pathlib import Path

import numpy as np
import onnx

STUDIO = Path(__file__).resolve().parents[2]
OUT = STUDIO / "launcher" / "static" / "img" / "intro" / "compile"
STAGE = (1600, 1000)
BOX = (110, 250, 1490, 750)   # graph 가 놓이는 자리 (x0, y0, x1, y1) — 아래는 prompt 자리


def kind(op: str) -> str:
    if op == "Conv":
        return "conv"
    if op in ("Sigmoid", "Mul"):   # SiLU = x · sigmoid(x)
        return "act"
    return "other"


def layout(model: onnx.ModelProto):
    """가로는 깊이 (흐름의 방향), 세로는 힘으로 푼다 — 이어진 node 는 당기고, 가까운 node 는 밀어낸다.

    처음엔 세로를 부모 평균에 두는 층 layout 이었다. 가장 충실하지만 이 model 은 대부분 한 줄로 이어진
    사슬이라 (깊이 301층) 가로선 하나에 점이 늘어선 모양이 됐다 — 밋밋해서 신경망으로 읽히지 않았다.
    연결은 그대로 두고 배치만 풀었다 (2026-09-30 사용자 결정). seed 를 고정해 굽힐 때마다 같다."""
    nodes = list(model.graph.node)
    producer = {out: i for i, n in enumerate(nodes) for out in n.output}
    parents = [sorted({producer[x] for x in n.input if x in producer}) for n in nodes]
    edges = [(p, i) for i, ps in enumerate(parents) for p in ps]

    depth = [0] * len(nodes)
    for i, ps in enumerate(parents):          # ONNX node 는 위상 순서로 온다
        depth[i] = max((depth[p] + 1 for p in ps), default=0)

    x0, y0, x1, y1 = BOX
    d = np.array(depth, float)
    x = x0 + (x1 - x0) * d / (d.max() or 1)
    y = np.random.default_rng(3).normal(0, 1, len(nodes)) * 60
    e = np.array(edges)
    for _ in range(400):
        f = np.zeros(len(nodes))
        pull = y[e[:, 1]] - y[e[:, 0]]
        np.add.at(f, e[:, 0], 0.06 * pull)
        np.add.at(f, e[:, 1], -0.06 * pull)
        dx, dy = x[:, None] - x[None, :], y[:, None] - y[None, :]
        near = (np.abs(dx) < 42) & (np.abs(dy) < 90) & ((dx ** 2 + dy ** 2) > 0)
        f += np.where(near, np.sign(dy + 1e-6) * (90 - np.abs(dy)) / 90 * 2.2, 0).sum(1)
        f -= 0.004 * y
        y += np.clip(f, -6, 6)
    y = (y0 + y1) / 2 + (y - y.mean()) / (np.abs(y - y.mean()).max() or 1) * (y1 - y0) / 2
    pts = [[int(round(x[i])), int(round(y[i])), kind(n.op_type)] for i, n in enumerate(nodes)]
    return pts, edges, depth


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--onnx", type=Path, required=True)
    ap.add_argument("--dxnn", type=Path, required=True)
    ap.add_argument("--fps", type=str, default=None)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    model = onnx.load(str(args.onnx))
    meta = {p.key: p.value for p in model.metadata_props}
    pts, edges, depth = layout(model)
    data = {"stage": list(STAGE), "nodes": pts, "edges": [list(e) for e in edges]}
    (args.out / "graph.json").write_text(json.dumps(data, separators=(",", ":")) + "\n", encoding="utf-8")

    ops = Counter(n.op_type for n in model.graph.node)
    params = sum(int(__import__("math").prod(t.dims)) for t in model.graph.initializer)
    lines = [
        "# intro Compiler 장면 — 출처",
        "",
        f"`scripts/intro/bake_compile.py` 가 {datetime.date.today().isoformat()} 에 구웠다. 손으로 고치지 않는다.",
        "",
        f"- graph: `{args.onnx.name}` — {meta.get('author', '?')} {meta.get('description', '').split(' trained')[0]} "
        f"(v{meta.get('version', '?')}, imgsz {meta.get('imgsz', '?')})",
        f"- node {len(pts)} · edge {len(edges)} · 깊이 {max(depth) + 1} 층 · parameter {params:,}",
        "- op: " + " · ".join(f"{k} {v}" for k, v in ops.most_common()),
        f"- compile 결과: 공식 Model Zoo `{args.dxnn.name}` ({args.dxnn.stat().st_size / 1e6:.1f} MB, "
        f"onnx {args.onnx.stat().st_size / 1e6:.1f} MB)",
    ]
    if args.fps:
        lines.append(f"- DX-M1 처리량: `run_model -b` → **{args.fps} FPS** (NPU 3 core)")
    (args.out / "SOURCE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(pts)} nodes · {len(edges)} edges · {max(depth) + 1} layers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
