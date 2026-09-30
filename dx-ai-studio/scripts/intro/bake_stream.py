"""intro 의 Stream 장면을 굽는다 — 실제 영상 16채널 + DX-M1 이 낸 실제 detection.

spec: docs/superpowers/specs/2026-09-30-intro-stream-scene-design.md

make_scenes.py 가 사진을 쓰지 않은 이유는 둘이었다 — 사진마다 톤이 제각각이고, 가진 사진에는 AI
overlay 가 이미 구워져 있었다. 여기서는 둘 다 풀린다: 16칸에 grade 를 하나로 입히고 (wall), box 는
구운 그림이 아니라 좌표 (detections.json) 로 두어 화면이 직접 그리고 움직인다.

소재는 dx_stream demo 가 쓰는 DEEPX 공식 sample 영상 묶음이다 (repo 에 넣지 않는다):

    curl -s https://sdk.deepx.ai/res/video/sample_videos.tar.gz | tar -xz -C <videos>

추론은 공식 Model Zoo yolov5-s 320 을 dx_app 예제의 factory (pre/post processor, 기본 threshold)
그대로 DX-M1 에서 돌린다. dx_engine 과 NPU 가 있는 runtime venv 로 실행한다:

    dx-runtime/venv-dx-runtime/bin/python3 scripts/intro/bake_stream.py \\
        --videos <videos> --model <yolov5-s_320x320.dxnn> [--bench]
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

STUDIO = Path(__file__).resolve().parents[2]
SUITE = STUDIO.parent
EXAMPLES = SUITE / "dx-runtime" / "dx_app" / "src" / "python_example"
OUT = STUDIO / "launcher" / "static" / "img" / "intro" / "stream"
SOURCE_PACK = "https://sdk.deepx.ai/res/video/sample_videos.tar.gz"

# (영상, 초) — 4×4 를 행 순서로. 같은 영상을 두 번 쓸 때는 시점과 구도가 다른 순간을 고른다.
SHOTS = [
    ("dron-citry-road.mov", 3), ("cctv-city-road2.mov", 2), ("blackbox-city-road.mp4", 1), ("dance-group.mov", 3),
    ("carrierbag.mp4", 2), ("cctv-city-road.mov", 6), ("dron-citry-road2.mov", 2), ("dogs.mp4", 2),
    ("blackbox-city-road2.mov", 9), ("dance-solo.mov", 4), ("cctv-city-road2.mov", 8), ("dron-citry-road.mov", 12),
    ("dance-group2.mov", 10), ("dron-citry-road2.mov", 5), ("carrierbag.mp4", 5), ("blackbox-city-road2.mov", 3),
]
HERO = 1          # 교차로 — 위에서 내려다보는 CCTV 앵글, 큰 차량을 이 model 이 잘 잡는다
COLS = ROWS = 4
STAGE = (1600, 1000)   # 화면 좌표계 (16:10). 화면은 이 무대를 cover 로 채운다
GAP = 2                # 칸 사이 (무대 단위)
SCALE = 1.5            # atlas 해상도 = 무대 × SCALE
TILE = ((STAGE[0] - GAP * (COLS - 1)) / COLS, (STAGE[1] - GAP * (ROWS - 1)) / ROWS)


def frame(video: Path, t: float, tmp: Path) -> np.ndarray:
    out = tmp / f"{video.stem}_{t}.png"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(t), "-i", str(video), "-frames:v", "1", str(out)],
                   check=True)
    return cv2.imread(str(out))


def cover(img: np.ndarray, ratio: float) -> np.ndarray:
    h, w = img.shape[:2]
    if w / h > ratio:
        nw = int(round(h * ratio))
        x = (w - nw) // 2
        return img[:, x:x + nw]
    nh = int(round(w / ratio))
    y = (h - nh) // 2
    return img[y:y + nh]


def _duotone_lut() -> np.ndarray:
    """회색 0–255 → 남색 · 중간 청색 · 차가운 흰색 사이를 잇는 256 색 (RGB)."""
    black, mid, white = np.array((3, 8, 20)), np.array((38, 66, 100)), np.array((205, 225, 240))
    g = np.arange(256)[:, None]
    lo = black + (mid - black) * (g / 127)
    hi = mid + (white - mid) * ((g - 127) / 128)
    return np.where(g <= 127, lo, hi).astype(np.float32)


_LUT = _duotone_lut()


def grade(bgr: np.ndarray) -> np.ndarray:
    """16칸을 한 system 의 시선으로 묶는 grade — 남색 duotone 에 원색 18% 를 남긴다 (BGR in/out)."""
    rgb = bgr[..., ::-1].astype(np.float32)
    lum = rgb @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    base = np.clip(lum.mean() + (rgb - lum.mean()) * 1.25, 0, 255)             # 대비 1.25
    gray = np.clip(base @ np.array([0.299, 0.587, 0.114], dtype=np.float32), 0, 255).astype(np.uint8)
    out = (_LUT[gray] * 0.82 + base * 0.18) * 0.85
    return np.clip(out, 0, 255).astype(np.uint8)[..., ::-1]


class Detector:
    def __init__(self, model: Path):
        sys.path[:0] = [str(EXAMPLES), str(EXAMPLES / "object_detection" / "yolov5s_4")]
        from dx_engine import InferenceEngine
        from factory import Yolov5s_4Factory
        from common.utility.labels import get_coco_80_labels

        self.config = json.loads((EXAMPLES / "object_detection" / "yolov5s_4" / "config.json").read_text())
        self.ie = InferenceEngine(str(model))
        shape = self.ie.get_input_tensors_info()[0]["shape"]
        ih, iw = (shape[1], shape[2]) if shape[-1] in (1, 3) else (shape[2], shape[3])
        factory = Yolov5s_4Factory(self.config)
        self.pre = factory.create_preprocessor(iw, ih)
        self.post = factory.create_postprocessor(iw, ih)
        self.labels = get_coco_80_labels()

    def __call__(self, img: np.ndarray) -> list[dict]:
        tensor, ctx = self.pre.process(img)
        h, w = img.shape[:2]
        boxes = []
        for d in self.post.process(self.ie.run([tensor]), ctx):
            x0, y0, x1, y1 = (max(0.0, min(1.0, v)) for v in (d.box[0] / w, d.box[1] / h, d.box[2] / w, d.box[3] / h))
            if x1 - x0 < 0.004 or y1 - y0 < 0.004:
                continue
            name = d.class_name or self.labels[int(d.class_id)]
            boxes.append({"b": [round(x0, 4), round(y0, 4), round(x1, 4), round(y1, 4)], "c": name})
        return boxes


def bench(model: Path) -> str:
    out = subprocess.run(["run_model", "-m", str(model), "-b", "-t", "8", "-w", "20"],
                         capture_output=True, text=True, check=True).stdout
    return re.search(r"FPS\s*:\s*([\d.]+)", out).group(1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--videos", type=Path, required=True)
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--bench", action="store_true", help="run_model 로 NPU FPS 를 재서 SOURCE.md 에 적는다")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    detect = Detector(args.model)
    ratio = TILE[0] / TILE[1]
    atlas = np.zeros((round(STAGE[1] * SCALE), round(STAGE[0] * SCALE), 3), np.uint8)
    tiles = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, (name, t) in enumerate(SHOTS):
            img = cover(frame(args.videos / name, t, Path(tmp)), ratio)
            boxes = detect(img)
            r, c = divmod(i, COLS)
            x, y = c * (TILE[0] + GAP), r * (TILE[1] + GAP)
            x0, y0 = round(x * SCALE), round(y * SCALE)
            x1, y1 = round((x + TILE[0]) * SCALE), round((y + TILE[1]) * SCALE)
            atlas[y0:y1, x0:x1] = grade(cv2.resize(img, (x1 - x0, y1 - y0), interpolation=cv2.INTER_AREA))
            if i == HERO:
                hero = img
            tiles.append({"source": name, "t": t, "boxes": boxes})
            print(f"{i:2} {name:26} t={t:<3} {len(boxes):3} boxes")

    cv2.imwrite(str(args.out / "wall.webp"), atlas, [cv2.IMWRITE_WEBP_QUALITY, 74])
    cv2.imwrite(str(args.out / "hero.webp"), hero, [cv2.IMWRITE_WEBP_QUALITY, 66])
    data = {"stage": list(STAGE), "cols": COLS, "rows": ROWS, "gap": GAP, "hero": HERO, "tiles": tiles}
    (args.out / "detections.json").write_text(json.dumps(data, separators=(",", ":")) + "\n", encoding="utf-8")

    total = sum(len(t["boxes"]) for t in tiles)
    fps = bench(args.model) if args.bench else None
    lines = [
        "# intro Stream 장면 — 출처",
        "",
        f"`scripts/intro/bake_stream.py` 가 {datetime.date.today().isoformat()} 에 구웠다. 손으로 고치지 않는다.",
        "",
        f"- 영상: DEEPX 공식 sample 영상 묶음 `{SOURCE_PACK}` (dx_stream demo 용, 1080p)",
        f"- model: 공식 Model Zoo `{args.model.name}` (dx_app `Yolov5s_4Factory`, threshold {self_cfg(detect.config)})",
        f"- 결과: 16칸 · box {total}개 · 시작 화면은 {HERO}번 칸 (`{SHOTS[HERO][0]}`)",
    ]
    if fps:
        lines.append(f"- NPU 처리량: `run_model -b -t 8 -w 20` → **{fps} FPS** (DX-M1, NPU 3 core)")
    lines += ["", "| 칸 | 영상 | 초 | box |", "|---|---|---|---|"]
    lines += [f"| {i} | `{t['source']}` | {t['t']} | {len(t['boxes'])} |" for i, t in enumerate(tiles)]
    (args.out / "SOURCE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"total {total} boxes" + (f" · {fps} FPS" if fps else ""))
    return 0


def self_cfg(cfg: dict) -> str:
    return ", ".join(f"{k} {v}" for k, v in cfg.items())


if __name__ == "__main__":
    raise SystemExit(main())
