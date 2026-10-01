"""DX Model Zoo — 경로, 상수, 카테고리 정의."""
from shared.tasks import TaskTable
import importlib
import os
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent          # dx_modelzoo/
import shared.paths as _shared_paths
# Reload so that a reload of THIS module (as done by env-override tests, e.g.
# monkeypatch.setenv(...); importlib.reload(config)) re-reads the current
# environment via shared.paths' own env-honoring computation, rather than
# reusing a stale value cached from shared.paths' first import.
importlib.reload(_shared_paths)
from shared.paths import SUITE_ROOT, DX_APP_ROOT

CONFIG_FILE = DX_APP_ROOT / "config" / "test_models.conf"
ASSETS_DIR = DX_APP_ROOT / "assets"
MODELS_DIR = ASSETS_DIR / "models"
CPP_DIR = DX_APP_ROOT / "src" / "cpp_example"
PY_DIR = DX_APP_ROOT / "src" / "python_example"
BUILD_DIR = DX_APP_ROOT / "build_x86_64" / "src" / "cpp_example"
SAMPLE_DIR = DX_APP_ROOT / "sample"
SAMPLE_IMG_DIR = SAMPLE_DIR / "img"

STATIC_DIR = SCRIPT_DIR / "static"
TEMPLATES_DIR = SCRIPT_DIR / "templates"
DATA_DIR = SCRIPT_DIR / "data"
CATALOG_FILE = DATA_DIR / "model_catalog.json"

DEFAULT_PORT = 8094
# Inference is proxied to the dx_app server. The launcher may reassign dx_app to a
# free port when 8080 is held by a foreign process, so honor DX_APP_PORT from the
# environment (set by the launcher) instead of hardcoding 8080.
try:
    DX_APP_PORT = int(os.environ.get("DX_APP_PORT", "8080"))
except (TypeError, ValueError):
    DX_APP_PORT = 8080


def dx_app_port() -> int:
    """지금 dx_app 의 port — launcher 가 쓰는 port 파일 (DX_APP_PORT_FILE) 을 요청마다 읽는다. dx_app 이 재시작하면
    (watchdog · 홈) 새 임시 port 로 오는데, 시작할 때 받은 DX_APP_PORT 만 쓰면 Zoo 의 Run Inference 가 전부
    DX_APP_UNAVAILABLE 이었다 (2026-10-02 release audit). 파일이 없으면 DX_APP_PORT."""
    pf = os.environ.get("DX_APP_PORT_FILE", "").strip()
    if pf:
        try:
            return int(open(pf, encoding="utf-8").read().strip())
        except (OSError, ValueError):
            pass
    try:
        return int(os.environ.get("DX_APP_PORT", "") or DX_APP_PORT)
    except (TypeError, ValueError):
        return DX_APP_PORT


SERVER_NAME = "DX Model Zoo"

CATEGORIES = {
    "object_detection":     {"label_en": "Object Detection",      "label_ko": "객체 탐지",           "label_ja": "物体検出",              "label_es": "Detección de objetos",         "label_zh-CN": "目标检测",   "label_zh-TW": "物件偵測",   "icon": "task-object_detection"},
    "classification":       {"label_en": "Classification",        "label_ko": "분류",               "label_ja": "分類",                  "label_es": "Clasificación",                "label_zh-CN": "分类",       "label_zh-TW": "分類",       "icon": "task-classification"},
    "ppu":                  {"label_en": "PPU",                   "label_ko": "PPU",                "label_ja": "PPU",                   "label_es": "PPU",                          "label_zh-CN": "PPU",        "label_zh-TW": "PPU",        "icon": "task-ppu"},
    "instance_segmentation":{"label_en": "Instance Segmentation", "label_ko": "인스턴스 분할",       "label_ja": "インスタンスセグメンテーション", "label_es": "Segmentación de instancias",   "label_zh-CN": "实例分割",   "label_zh-TW": "實例分割",   "icon": "task-instance_segmentation"},
    "face_detection":       {"label_en": "Face Detection",        "label_ko": "얼굴 탐지",          "label_ja": "顔検出",                "label_es": "Detección de rostros",         "label_zh-CN": "人脸检测",   "label_zh-TW": "人臉偵測",   "icon": "task-face_detection"},
    "pose_estimation":      {"label_en": "Pose Estimation",       "label_ko": "자세 추정",          "label_ja": "姿勢推定",              "label_es": "Estimación de pose",           "label_zh-CN": "姿态估计",   "label_zh-TW": "姿態估計",   "icon": "task-pose_estimation"},
    "semantic_segmentation":{"label_en": "Semantic Segmentation", "label_ko": "시맨틱 분할",        "label_ja": "セマンティックセグメンテーション","label_es": "Segmentación semántica",       "label_zh-CN": "语义分割",   "label_zh-TW": "語意分割",   "icon": "task-semantic_segmentation"},
    "image_denoising":      {"label_en": "Image Denoising",       "label_ko": "이미지 노이즈 제거", "label_ja": "画像ノイズ除去",         "label_es": "Eliminación de ruido de imagen","label_zh-CN": "图像去噪",   "label_zh-TW": "影像去噪",   "icon": "task-image_denoising"},
    "obb_detection":        {"label_en": "OBB Detection",         "label_ko": "OBB 탐지",           "label_ja": "OBB検出",               "label_es": "Detección OBB",                "label_zh-CN": "OBB检测",    "label_zh-TW": "OBB偵測",    "icon": "task-obb_detection"},
    "reid":                 {"label_en": "Re-Identification",     "label_ko": "재식별",             "label_ja": "再識別",                "label_es": "Reidentificación",             "label_zh-CN": "重识别",     "label_zh-TW": "重新識別",   "icon": "task-reid"},
    "embedding":            {"label_en": "Embedding",             "label_ko": "임베딩",             "label_ja": "埋め込み",              "label_es": "Embedding",                    "label_zh-CN": "嵌入",       "label_zh-TW": "嵌入",       "icon": "task-embedding"},
    "attribute_recognition":{"label_en": "Attribute Recognition",  "label_ko": "속성 인식",          "label_ja": "属性認識",              "label_es": "Reconocimiento de atributos",  "label_zh-CN": "属性识别",   "label_zh-TW": "屬性辨識",   "icon": "task-attribute_recognition"},
    "super_resolution":     {"label_en": "Super Resolution",      "label_ko": "초해상도",           "label_ja": "超解像",                "label_es": "Superresolución",              "label_zh-CN": "超分辨率",   "label_zh-TW": "超解析度",   "icon": "task-super_resolution"},
    "face_alignment":       {"label_en": "Face Alignment",        "label_ko": "얼굴 정렬",          "label_ja": "顔アライメント",         "label_es": "Alineación facial",            "label_zh-CN": "人脸对齐",   "label_zh-TW": "人臉對齊",   "icon": "task-face_alignment"},
    "depth_estimation":     {"label_en": "Depth Estimation",      "label_ko": "깊이 추정",          "label_ja": "深度推定",              "label_es": "Estimación de profundidad",    "label_zh-CN": "深度估计",   "label_zh-TW": "深度估計",   "icon": "task-depth_estimation"},
    "image_enhancement":    {"label_en": "Image Enhancement",     "label_ko": "이미지 향상",        "label_ja": "画像強調",              "label_es": "Mejora de imagen",             "label_zh-CN": "图像增强",   "label_zh-TW": "影像增強",   "icon": "task-image_enhancement"},
    "hand_landmark":        {"label_en": "Hand Landmark",         "label_ko": "손 랜드마크",        "label_ja": "手のランドマーク",       "label_es": "Puntos de referencia de la mano","label_zh-CN": "手部关键点", "label_zh-TW": "手部關鍵點", "icon": "task-hand_landmark"},
    "hand_detection":       {"label_en": "Hand Detection",        "label_ko": "손 탐지",            "label_ja": "手検出",                "label_es": "Detección de manos",           "label_zh-CN": "手部检测",   "label_zh-TW": "手部偵測",   "icon": "task-hand_detection"},
    "keypoint_detection":   {"label_en": "Keypoint Detection",    "label_ko": "키포인트 탐지",      "label_ja": "キーポイント検出",       "label_es": "Detección de puntos clave",    "label_zh-CN": "关键点检测", "label_zh-TW": "關鍵點偵測", "icon": "task-keypoint_detection"},
    "object_pose_estimation":{"label_en": "Object Pose Estimation","label_ko": "객체 자세 추정",     "label_ja": "物体姿勢推定",          "label_es": "Estimación de pose de objetos","label_zh-CN": "物体姿态估计","label_zh-TW": "物件姿態估計","icon": "task-object_pose_estimation"},
    "panoptic_driving_perception":{"label_en": "Panoptic Driving Perception","label_ko": "파놉틱 주행 인식","label_ja": "パノプティック走行認識","label_es": "Percepción panóptica de conducción","label_zh-CN": "全景驾驶感知","label_zh-TW": "全景駕駛感知","icon": "task-panoptic_driving_perception"},
    "3d_object_detection":  {"label_en": "3D Object Detection",   "label_ko": "3D 객체 탐지",       "label_ja": "3D物体検出",            "label_es": "Detección de objetos 3D",      "label_zh-CN": "3D目标检测", "label_zh-TW": "3D物件偵測", "icon": "task-3d_object_detection"},
    # dx_app per-model layout 의 task key (spec 2026-10-01) — 옛 key 와의 짝은 shared/tasks.py LEGACY_TO_TASK
    "image_classification": {"label_en": "Image Classification", "label_ko": "이미지 분류", "label_ja": "画像分類", "label_es": "Clasificación de imágenes", "label_zh-CN": "图像分类", "label_zh-TW": "影像分類", "icon": "task-image_classification"},
    "oriented_object_detection": {"label_en": "Oriented Object Detection", "label_ko": "회전 객체 탐지", "label_ja": "回転物体検出", "label_es": "Detección de objetos orientados", "label_zh-CN": "旋转目标检测", "label_zh-TW": "旋轉物件偵測", "icon": "task-oriented_object_detection"},
    "face_landmark": {"label_en": "Face Landmark", "label_ko": "얼굴 랜드마크", "label_ja": "顔ランドマーク", "label_es": "Puntos faciales", "label_zh-CN": "人脸关键点", "label_zh-TW": "人臉關鍵點", "icon": "task-face_landmark"},
    "face_recognition": {"label_en": "Face Recognition", "label_ko": "얼굴 인식", "label_ja": "顔認識", "label_es": "Reconocimiento facial", "label_zh-CN": "人脸识别", "label_zh-TW": "人臉辨識", "icon": "task-face_recognition"},
    "person_attribute": {"label_en": "Person Attribute", "label_ko": "사람 속성", "label_ja": "人物属性", "label_es": "Atributos de persona", "label_zh-CN": "行人属性", "label_zh-TW": "行人屬性", "icon": "task-person_attribute"},
    "low_light_enhancement": {"label_en": "Low-Light Enhancement", "label_ko": "저조도 향상", "label_ja": "低照度補正", "label_es": "Mejora con poca luz", "label_zh-CN": "低光增强", "label_zh-TW": "低光增強", "icon": "task-low_light_enhancement"},
    "person_reid": {"label_en": "Person Re-ID", "label_ko": "사람 재식별", "label_ja": "人物再識別", "label_es": "Re-ID de personas", "label_zh-CN": "行人重识别", "label_zh-TW": "行人重新識別", "icon": "task-person_reid"},
    "anomaly_detection": {"label_en": "Anomaly Detection", "label_ko": "이상 탐지", "label_ja": "異常検知", "label_es": "Detección de anomalías", "label_zh-CN": "异常检测", "label_zh-TW": "異常偵測", "icon": "task-anomaly_detection"},
    "zero_shot_image_classification": {"label_en": "Zero-Shot Classification", "label_ko": "제로샷 분류", "label_ja": "ゼロショット分類", "label_es": "Clasificación zero-shot", "label_zh-CN": "零样本分类", "label_zh-TW": "零樣本分類", "icon": "task-zero_shot_image_classification"},
    "zero_shot_instance_segmentation": {"label_en": "Zero-Shot Segmentation", "label_ko": "제로샷 분할", "label_ja": "ゼロショットセグメンテーション", "label_es": "Segmentación zero-shot", "label_zh-CN": "零样本分割", "label_zh-TW": "零樣本分割", "icon": "task-zero_shot_instance_segmentation"},
    "image_matting": {"label_en": "Image Matting", "label_ko": "이미지 매팅", "label_ja": "画像マッティング", "label_es": "Matting de imagen", "label_zh-CN": "图像抠图", "label_zh-TW": "影像去背", "icon": "task-image_matting"},
    "image_retrieval": {"label_en": "Image Retrieval", "label_ko": "이미지 검색", "label_ja": "画像検索", "label_es": "Recuperación de imágenes", "label_zh-CN": "图像检索", "label_zh-TW": "影像檢索", "icon": "task-image_retrieval"},
    "visual_place_recognition": {"label_en": "Visual Place Recognition", "label_ko": "장소 인식", "label_ja": "視覚的場所認識", "label_es": "Reconocimiento visual de lugares", "label_zh-CN": "视觉地点识别", "label_zh-TW": "視覺地點辨識", "icon": "task-visual_place_recognition"},
    "face_attribute": {"label_en": "Face Attribute", "label_ko": "얼굴 속성", "label_ja": "顔属性", "label_es": "Atributos faciales", "label_zh-CN": "人脸属性", "label_zh-TW": "人臉屬性", "icon": "task-face_attribute"},
}

# 태스크별 Example 이미지 표시 타입
# TaskTable: 새 task key (image_classification …) 로 물어도 옛 key 의 값을 찾는다 (shared/tasks.py)
EXAMPLE_TYPES = TaskTable({
    "object_detection": "single", "face_detection": "single",
    "pose_estimation": "single", "obb_detection": "single",
    "ppu": "single", "face_alignment": "single", "hand_landmark": "single",
    "attribute_recognition": "single", "embedding": "single",
    "image_denoising": "before_after", "super_resolution": "before_after",
    "image_enhancement": "before_after",
    "semantic_segmentation": "overlay", "instance_segmentation": "overlay",
    "depth_estimation": "overlay",
    "classification": "classified", "reid": "gallery",
    "hand_detection": "single", "keypoint_detection": "single",
    "object_pose_estimation": "single", "3d_object_detection": "single",
    "panoptic_driving_perception": "overlay",
    "anomaly_detection": "overlay", "image_matting": "overlay", "zero_shot_instance_segmentation": "overlay",
    "zero_shot_image_classification": "classified", "image_retrieval": "gallery",
    "visual_place_recognition": "gallery", "face_attribute": "single",
})

# 태스크별 기본 샘플 이미지 (inference 용)
# dx_app 이 v3.2.0/v3.2.1 에서 샘플을 교체했는데 이 표가 따라가지 않아, 한 달 넘게
# 없는 파일을 가리키고 있었다. server.py 의 기본 이미지 선택은 파일명이 목록에 없으면
# 조용히 `images[0]` 으로 떨어지므로 오류 없이 엉뚱한 그림이 떴다 —
# 초해상도 데모에 위성사진이 나오는 식이었다.
#
#   680366d (v3.2.0-rc) dota8_test/ 10장(93MB) 삭제 → sample_airport_satellite_view.png 추가
#   c6c35e4 (v3.2.1-rc) sample_superresolution.png 삭제 → sample_lowres275x150.png 추가
#
# 둘 다 같은 커밋에서 대체물을 함께 넣었다. 자산이 사라진 것이 아니라 교체된 것이다.
# 진짜 출처는 dx_app/scripts/run_examples.sh 의 CATEGORY_IMAGE 표이고,
# 이제 tests/dx_modelzoo/test_conf_categories_are_known.py 가 어긋나면 말한다.
SAMPLE_IMAGES = TaskTable({
    "object_detection": "sample/img/sample_street.jpg",
    "face_detection": "sample/img/sample_face.jpg",
    "pose_estimation": "sample/img/sample_people.jpg",
    "obb_detection": "sample/img/sample_airport_satellite_view.png",
    "classification": "sample/img/sample_dog.jpg",
    "instance_segmentation": "sample/img/sample_street.jpg",
    "semantic_segmentation": "sample/img/sample_parking.jpg",
    "depth_estimation": "sample/img/sample_horse.jpg",
    "image_denoising": "sample/img/sample_denoising.jpg",
    "super_resolution": "sample/img/sample_lowres275x150.png",
    "image_enhancement": "sample/img/sample_lowlight.jpg",
    "embedding": "sample/img/face_pair",
    "attribute_recognition": "sample/img/sample_person_a1.jpg",
    "reid": "sample/img/person_pair",
    "ppu": "sample/img/sample_street.jpg",
    "hand_landmark": "sample/img/sample_hand.jpg",
    "face_alignment": "sample/img/sample_face_a1.jpg",
    "hand_detection": "sample/img/sample_hand.jpg",
    "keypoint_detection": "sample/img/sample_street.jpg",
    "object_pose_estimation": "sample/dope/000000.png",
    "panoptic_driving_perception": "sample/img/sample_parking.jpg",
    "3d_object_detection": "sample/kitti/velodyne/000049.bin",
    # dx_app per-model layout 의 새 task — 그 예제들의 config.json default_image (8d0b748)
    "anomaly_detection": "sample/img/sample_parking.jpg",
    "zero_shot_image_classification": "sample/img/sample_dog.jpg",
    "zero_shot_instance_segmentation": "sample/img/sample_street.jpg",
    "image_matting": "sample/img/sample_person_b.jpg",
    "image_retrieval": "sample/img/sample_person_a2.jpg",
    "visual_place_recognition": "sample/vpr/queries/q1.jpg",
    "face_attribute": "sample/img/sample_person_a1.jpg",
})

# per-model dx_app (8d0b748) 의 person ReID (reid ↔ person_reid) 는 사람 쌍 폴더가 아니라 query 한 장 + gallery
# (sample/gallery/*.bin) 다 — 그 예제의 config.json default_image · run_examples.sh 의 [person_reid]. main 은 쌍 폴더.
from shared import dx_app_layout as _layout
if _layout.detect(DX_APP_ROOT) == _layout.PER_MODEL:
    SAMPLE_IMAGES["reid"] = "sample/reid/queries/sample_person_a2.jpg"

MODEL_IMAGE_OVERRIDE = {
    "scrfd500m_ppu": "sample/img/sample_face.jpg",
    "yolov5pose_ppu": "sample/img/sample_people.jpg",
    "handlandmarklite_1": "sample/img/sample_hand.jpg",
    "unet_mobilenet_v2": "sample/img/sample_dog.jpg",
}

for _name, _path in [("DX_APP_ROOT", DX_APP_ROOT)]:
    if not _path.is_dir():
        print(f"[WARNING] {_name} not found: {_path}")
