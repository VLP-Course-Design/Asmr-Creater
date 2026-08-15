"""
test_vision.py —— 第二人视觉层完整功能测试套件

覆盖：预处理 / JSONL 校验 / 实体匹配 / 融合输出 / 批量处理 /
      Schema 校验 / 坐标映射 / VLM 格式归一化

用法: python scripts/test_vision.py
"""

import sys, os, json, tempfile, warnings
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

import numpy as np
import cv2


def test_1_preprocessing():
    """预处理管线：Letterbox 形状、VLM 缩放、字段完整性"""
    print("=" * 50)
    print("Test 1: Preprocessing pipeline")
    print("=" * 50)

    from vision.preprocess import load_and_preprocess_image

    test_img = np.random.randint(0, 255, (300, 400, 3), dtype=np.uint8)
    test_path = str(REPO_ROOT / "_test_tmp.jpg")
    # 用 Pillow 写图,与产品代码一致:cv2.imwrite 在含中文/非 ASCII 的路径下会静默失败
    from PIL import Image
    Image.fromarray(test_img).save(test_path)  # test_img 已是 RGB,无需 cvtColor

    result = load_and_preprocess_image(test_path,
                                       target_size_yolo=(640, 640),
                                       target_size_vlm=(224, 224))
    assert result is not None, "load_and_preprocess_image returned None"
    assert result['image_yolo'].shape == (640, 640, 3)
    assert result['image_vlm'].shape == (224, 224, 3)
    for k in ['image', 'image_yolo', 'image_vlm', 'original_height',
              'original_width', 'scale', 'pad_left', 'pad_top',
              'new_width', 'new_height', 'path', 'brightness']:
        assert k in result, f"Missing field: {k}"
    assert 0.0 <= result['brightness'] <= 1.0
    print(f"  image_yolo: {result['image_yolo'].shape}")
    print(f"  image_vlm: {result['image_vlm'].shape}")
    print(f"  scale={result['scale']:.4f} pad_left={result['pad_left']} pad_top={result['pad_top']}")
    print("  PASS\n")
    os.remove(test_path)


def test_2_load_jsonl():
    """load_jsonl：正常解析、缺字段警告、空行/损坏行容错"""
    print("=" * 50)
    print("Test 2: load_jsonl field validation")
    print("=" * 50)

    from vision.vlm_yolo_fusion import load_jsonl

    tmp_dir = tempfile.mkdtemp()
    jp = os.path.join(tmp_dir, 'test.jsonl')
    with open(jp, 'w', encoding='utf-8') as f:
        f.write(json.dumps({
            'image': 't.jpg', 'path': 'd/t.jpg',
            'global_vibe': {'scene_type': 'r', 'mood': 'calm', 'brightness': 0.5,
                            'warmth': 'neutral', 'base_noise': 'pink', 'time_of_day': 'night'},
            'suggested_entities': [{'name': 'cat', 'state': 'sleeping'}]
        }, ensure_ascii=False) + '\n')
        f.write(json.dumps({'image': 'b.jpg', 'path': 'd/b.jpg'}) + '\n')
        f.write('\n')
        f.write('not json\n')

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        records = load_jsonl(jp)
        missing = [x for x in w if 'missing' in str(x.message).lower() or '缺少字段' in str(x.message)]

    assert len(records) == 2
    assert records[0]['image'] == 't.jpg'
    assert 'global_vibe' not in records[1]
    assert len(missing) >= 1
    print(f"  Records: {len(records)}, warnings: {len(missing)}")
    print("  PASS\n")
    import shutil; shutil.rmtree(tmp_dir)


def test_3_entity_matching():
    """实体匹配：精确/大小写/复数/无匹配"""
    print("=" * 50)
    print("Test 3: Entity matching strategies")
    print("=" * 50)

    from vision.vlm_yolo_fusion import _match_entity_to_yolo
    from vision.detector import Detection

    dets = [
        Detection(name='cat', x=0.3, depth='near', conf=0.9, bbox=[0.1, 0.1, 0.3, 0.5]),
        Detection(name='person', x=0.7, depth='mid', conf=0.85, bbox=[0.6, 0.1, 0.8, 0.7]),
        Detection(name='bus', x=0.6, depth='far', conf=0.8, bbox=[0.4, 0.2, 0.7, 0.5]),
    ]

    idx, det = _match_entity_to_yolo('cat', dets)
    assert idx == 0 and det.name == 'cat'; print("  exact: cat -> cat")

    idx, det = _match_entity_to_yolo('CAT', dets)
    assert idx == 0 and det.name == 'cat'; print("  case: CAT -> cat")

    idx, det = _match_entity_to_yolo('cats', dets)
    assert idx == 0 and det.name == 'cat'; print("  plural: cats -> cat")

    idx, det = _match_entity_to_yolo('X', dets)
    assert idx is None; print("  no-match: X -> None")

    print("  PASS\n")


def test_4_merge_payload():
    """merge_structured_payload：Scene Contract 输出格式"""
    print("=" * 50)
    print("Test 4: merge_structured_payload output")
    print("=" * 50)

    from vision.vlm_yolo_fusion import merge_structured_payload
    from vision.detector import Detection

    yolo = {
        'image_path': 'd/test.jpg', 'original_width': 800, 'original_height': 600,
        'error': None,
        'detections': [
            Detection(name='cat', x=0.22, depth='near', conf=0.91,
                      bbox=[0.22, 0.17, 0.44, 0.83]),
            Detection(name='person', x=0.75, depth='mid', conf=0.85,
                      bbox=[0.75, 0.03, 0.88, 0.67]),
        ]
    }
    vlm = {
        'image': 'test.jpg', 'path': 'd/test.jpg',
        'global_vibe': {'scene_type': 'bedroom', 'mood': 'calm', 'brightness': 0.28,
                        'warmth': 'cool', 'base_noise': 'brown', 'time_of_day': 'night'},
        'suggested_entities': [
            {'name': 'cat', 'state': 'sleeping'},
            {'name': 'person', 'state': 'standing'},
            {'name': 'X', 'state': 'diffusing'},
        ]
    }
    merged = merge_structured_payload(yolo, vlm)
    assert merged['schema_version'] == '1.0'
    entities = merged['entities']
    assert len(entities) == 3

    cat = entities[0]
    assert cat['name'] == 'cat' and cat['source'] == 'yolo' and cat['depth'] == 'near'
    print(f"  cat: source={cat['source']} depth={cat['depth']} x={cat['x']} conf={cat['conf']}")

    person = entities[1]
    assert person['name'] == 'person' and person['source'] == 'yolo' and person['depth'] == 'mid'
    print(f"  person: source={person['source']} depth={person['depth']} x={person['x']}")

    x_ent = entities[2]
    assert x_ent['name'] == 'X' and x_ent['source'] == 'vlm'
    assert x_ent['x'] == 0.5 and x_ent['depth'] == 'mid' and x_ent['conf'] == 0.5
    print(f"  X: source={x_ent['source']} depth={x_ent['depth']} x={x_ent['x']}")

    print("  PASS\n")


def test_5_process_batch():
    """process_batch：成功+失败条目"""
    print("=" * 50)
    print("Test 5: process_batch")
    print("=" * 50)

    from vision.vlm_yolo_fusion import process_batch
    from vision.detector import Detection

    yolo_results = [{
        'image_path': 'd/test.jpg', 'original_width': 800, 'original_height': 600,
        'error': None,
        'detections': [
            Detection(name='cat', x=0.22, depth='near', conf=0.91,
                      bbox=[0.22, 0.17, 0.44, 0.83]),
        ]
    }]
    vlm_ok = [{'image': 'test.jpg', 'path': 'd/test.jpg',
               'global_vibe': {'scene_type': 'b', 'mood': 'calm', 'brightness': 0.28,
                               'warmth': 'cool', 'base_noise': 'brown', 'time_of_day': 'night'},
               'suggested_entities': [{'name': 'cat', 'state': 's'}]}]
    vlm_fail = [{'image': 'corrupt.jpg', 'path': 'd/corrupt.jpg', 'error': 'VLM timeout'}]

    batch = process_batch(yolo_results, vlm_ok, vlm_fail)
    assert len(batch) == 2
    assert len(batch[0]['entities']) == 1 and batch[0]['entities'][0]['source'] == 'yolo'
    assert batch[1]['image'].get('error') == 'VLM timeout'
    assert batch[1]['entities'] == []
    print(f"  Success entry: {len(batch[0]['entities'])} entity")
    print(f"  Failed entry: error='{batch[1]['image']['error']}'")
    print("  PASS\n")


def test_6_schema_validation():
    """Scene Contract schema 校验"""
    print("=" * 50)
    print("Test 6: Scene Contract schema validation")
    print("=" * 50)

    from vision.vlm_yolo_fusion import merge_structured_payload
    from vision.detector import Detection
    from common.contract import validate_scene

    yolo = {
        'image_path': 'd/bedroom.jpg', 'original_width': 1024, 'original_height': 768,
        'error': None,
        'detections': [
            Detection(name='cat', x=0.22, depth='near', conf=0.91,
                      bbox=[0.22, 0.20, 0.44, 0.85]),
        ]
    }
    vlm = {
        'image': 'bedroom.jpg', 'path': 'd/bedroom.jpg',
        'global_vibe': {'scene_type': 'bedroom', 'mood': 'calm', 'brightness': 0.28,
                        'warmth': 'cool', 'base_noise': 'brown', 'time_of_day': 'night'},
        'suggested_entities': [
            {'name': 'cat', 'state': 'sleeping'},
            {'name': 'window', 'state': 'rainy'},
        ]
    }
    output = merge_structured_payload(yolo, vlm)
    validated = validate_scene(output)
    assert validated is not None
    print("  Output passed Scene Contract JSON Schema validation")
    print("  PASS\n")


def test_7_coordinate_mapping():
    """坐标映射：horizontal/distance 阈值"""
    print("=" * 50)
    print("Test 7: Coordinate mapping thresholds")
    print("=" * 50)

    from vision.yolo import YoloDetector

    assert YoloDetector._compute_horizontal(200, 800) == 'left'
    assert YoloDetector._compute_horizontal(400, 800) == 'center'
    assert YoloDetector._compute_horizontal(600, 800) == 'right'
    assert YoloDetector._compute_horizontal(263, 800) == 'left'   # 0.328 < 0.33
    assert YoloDetector._compute_horizontal(537, 800) == 'right'  # 0.671 > 0.67
    print("  horizontal: left/center/right thresholds correct")

    img_area = 800 * 600
    assert YoloDetector._compute_distance([0, 0, 400, 400], 800, 600) == 'near'
    assert YoloDetector._compute_distance([0, 0, 300, 300], 800, 600) == 'medium'
    assert YoloDetector._compute_distance([0, 0, 150, 150], 800, 600) == 'far'
    print("  distance: near/medium/far thresholds correct")
    print("  PASS\n")


def test_8_vlm_format_normalization():
    """VLM 格式归一化：字符串/嵌套列表/非标准类型容错"""
    print("=" * 50)
    print("Test 8: VLM format normalization")
    print("=" * 50)

    from vision.vlm_yolo_fusion import merge_structured_payload

    yolo = {
        'image_path': 'd/test.jpg', 'original_width': 800, 'original_height': 600,
        'error': None, 'detections': []
    }
    vlm = {
        'image': 'test.jpg', 'path': 'd/test.jpg',
        'global_vibe': {'scene_type': 'room', 'mood': 'calm', 'brightness': 0.5,
                        'warmth': 'neutral', 'base_noise': 'pink', 'time_of_day': 'night'},
        'suggested_entities': [
            {'name': 'cat', 'state': 'sleeping'},   # normal dict
            'person',                                 # bare string
            ['dog', 'bird'],                          # nested list
            123,                                      # number (should be skipped)
            {'name': 'window', 'state': 'rainy'},    # normal dict
        ]
    }

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        merged = merge_structured_payload(yolo, vlm)

    entities = merged['entities']

    # 5 inputs, 1 skipped (123) = 4 outputs
    assert len(entities) == 4, f"Expected 4 entities, got {len(entities)}"
    assert entities[0]['name'] == 'cat'
    assert entities[1]['name'] == 'person'     # string -> {"name":"person"}
    assert entities[2]['name'] == 'dog, bird'  # list -> joined
    assert entities[3]['name'] == 'window'

    # 3 warnings expected (str, list, int)
    assert len(w) == 3, f"Expected 3 warnings, got {len(w)}"
    assert 'string' in str(w[0].message).lower() or '字符串' in str(w[0].message)
    assert 'list' in str(w[1].message).lower() or '列表' in str(w[1].message)
    assert 'int' in str(w[2].message).lower()

    print(f"  Input: [dict, str, list, int, dict] -> Output: {len(entities)} entities")
    for e in entities:
        print(f"    name={e['name']!r}  source={e['source']}")
    print(f"  Warnings: {len(w)} (str + list + int)")
    print("  PASS\n")


def test_9_exif_and_path_sanitize():
    """EXIF 转正后宽高对调；绝对路径被收成相对文件名"""
    print("=" * 50)
    print("Test 9: EXIF orientation + path sanitization")
    print("=" * 50)

    from PIL import Image
    from vision.preprocess import apply_exif_orientation, load_and_preprocess_image
    from vision.visual_record import sanitize_relative_path, sanitize_record_id

    tmp = REPO_ROOT / "_test_exif.jpg"
    img = Image.new("RGB", (200, 100), (200, 30, 30))
    exif = img.getexif()
    exif[274] = 6  # Orientation: rotate 90 CW → 100x200
    img.save(tmp, format="JPEG", exif=exif)

    oriented = apply_exif_orientation(str(tmp))
    assert oriented is not None
    assert oriented.shape[0] == 200 and oriented.shape[1] == 100, oriented.shape
    print(f"  EXIF 6: 200x100 -> {oriented.shape[1]}x{oriented.shape[0]}")

    result = load_and_preprocess_image(str(tmp))
    assert result is not None
    assert result["original_width"] == 100 and result["original_height"] == 200
    print(f"  preprocess size: {result['original_width']}x{result['original_height']}")

    assert sanitize_relative_path(r"C:\Users\demo\AppData\Local\Temp\a.jpg") == "a.jpg"
    assert sanitize_relative_path("/tmp/secret/b.jpg") == "b.jpg"
    assert sanitize_relative_path("img_dataset/Train/42.jpg") == "img_dataset/Train/42.jpg"
    assert sanitize_record_id("42.jpg") == "42"
    print("  path sanitize: absolute stripped, relative kept")
    print("  PASS\n")
    tmp.unlink(missing_ok=True)


def test_10_v23_visual_record():
    """v2.3 记录可被播放计划转换器 validate_record 接受"""
    print("=" * 50)
    print("Test 10: visual record v2.3 for playback")
    print("=" * 50)

    from vision.detector import Detection
    from vision.anchor_map import map_name_to_anchor
    from vision.visual_record import build_visual_record_v23
    from audio.playback_converter import build_anchor_mapping, load_mapping_config, validate_record

    assert map_name_to_anchor("bird") == "visible_bird"
    assert map_name_to_anchor("cat", "sleeping") == "relaxed_or_sleeping_cat"
    assert map_name_to_anchor("cat", "running") is None
    assert map_name_to_anchor("person") is None
    assert map_name_to_anchor("person", "walking") == "walking_person"
    print("  anchor map: bird/cat/person rules ok")

    yolo = {
        "image_path": "img_dataset/Train/test.jpg",
        "original_width": 800,
        "original_height": 600,
        "brightness": 0.42,
        "error": None,
        "detections": [
            Detection(name="bird", x=0.84, depth="far", conf=0.78,
                      bbox=[0.82, 0.21, 0.87, 0.25]),
            Detection(name="cat", x=0.22, depth="near", conf=0.91,
                      bbox=[0.12, 0.20, 0.32, 0.85]),
            Detection(name="person", x=0.70, depth="mid", conf=0.80,
                      bbox=[0.60, 0.10, 0.80, 0.90]),
        ],
    }
    vlm = {
        "image": "test.jpg",
        "path": r"C:\Users\demo\Temp\test.jpg",
        "global_vibe": {
            "scene_type": "beach",
            "mood": "gloomy",
            "brightness": 0.99,
            "warmth": "warm",
            "base_noise": "brown",
            "time_of_day": "dusk",
        },
        "suggested_entities": [
            {"name": "cat", "state": "sleeping"},
            {"name": "bird", "state": "flying"},
            {"name": "person", "state": "standing"},
        ],
    }
    record = build_visual_record_v23(yolo, vlm)
    assert record is not None
    assert record["schema_version"] == "2.3"
    assert record["image"]["path"] == "test.jpg"
    assert record["global_vibe"]["brightness"] == 0.42
    assert record["global_vibe"]["mood"] == "melancholic"
    assert record["global_vibe"]["scene_type"] == "beach"
    assert record["global_vibe"]["scene_group"] == "water_coastal"
    assert "base_noise" not in record["global_vibe"]
    ids = {a["anchor_id"] for a in record["trigger_anchors"]}
    assert "visible_bird" in ids
    assert "relaxed_or_sleeping_cat" in ids
    assert "walking_person" not in ids
    for anchor in record["trigger_anchors"]:
        assert "depth_hint" not in anchor
    print(f"  anchors: {sorted(ids)}")

    _, _, _, visual_spec = load_mapping_config(REPO_ROOT / "configs" / "playback")
    allowed, _ = build_anchor_mapping(visual_spec)
    validate_record(record, allowed)
    print("  playback_converter.validate_record: ok")
    print("  PASS\n")


def test_11_handover_v23_input():
    """handover_v23 JSONL（无 bbox）+ YOLO 框 → 带 bbox_norm 的正式记录"""
    print("=" * 50)
    print("Test 11: handover v2.3 input + YOLO boxes")
    print("=" * 50)

    from vision.detector import Detection
    from vision.vlm_yolo_fusion import load_jsonl, merge_structured_payload, process_batch
    from vision.visual_record import (
        build_visual_record_v23,
        normalize_upstream_record,
        process_batch_v23,
    )
    from common.contract import validate_scene
    from audio.playback_converter import build_anchor_mapping, load_mapping_config, validate_record

    handover = {
        "schema_version": "2.3",
        "id": "1014",
        "image": {"path": "data/Train/1014.jpg", "width": 2508, "height": 3440},
        "global_vibe": {
            "scene_type": "forest",
            "secondary_scene_types": ["stream"],
            "scene_group": "forest_vegetation",
            "mood": "calm",
            "warmth": "cool",
            "time_of_day": "afternoon",
            "brightness": 0.99,
        },
        "trigger_anchors": [
            {"anchor_id": "visible_bird", "confidence": 0.5, "source": "vlm_legacy"},
            {
                "anchor_id": "relaxed_or_sleeping_cat",
                "confidence": 0.5,
                "source": "vlm_legacy",
                "state_note": "sleeping",
            },
        ],
    }
    norm = normalize_upstream_record(handover)
    assert norm["image"] == "1014.jpg"
    assert norm["path"] == "data/Train/1014.jpg"
    assert {e["name"] for e in norm["suggested_entities"]} >= {
        "visible_bird", "relaxed_or_sleeping_cat",
    }
    print("  normalize: id/path/anchors -> suggested_entities")

    yolo = {
        "image_path": "img_dataset/Train/1014.jpg",
        "original_width": 800,
        "original_height": 600,
        "brightness": 0.41,
        "error": None,
        "detections": [
            Detection(name="bird", x=0.20, depth="far", conf=0.88,
                      bbox=[0.10, 0.10, 0.30, 0.25]),
            Detection(name="cat", x=0.55, depth="near", conf=0.93,
                      bbox=[0.40, 0.30, 0.70, 0.90]),
        ],
    }
    record = build_visual_record_v23(yolo, handover)
    assert record["id"] == "1014"
    assert record["global_vibe"]["scene_group"] == "forest_vegetation"
    assert record["global_vibe"]["brightness"] == 0.41
    assert record["global_vibe"]["secondary_scene_types"] == ["stream"]
    ids = {a["anchor_id"] for a in record["trigger_anchors"]}
    assert ids == {"visible_bird", "relaxed_or_sleeping_cat"}
    for a in record["trigger_anchors"]:
        box = a["bbox_norm"]
        assert box["format"] == "xyxy"
        assert box["x_min"] < box["x_max"]
        assert "depth_hint" not in a
    print(f"  v2.3 anchors with bbox: {sorted(ids)}")

    v1 = merge_structured_payload(yolo, handover)
    validate_scene(v1)
    assert v1["schema_version"] == "1.0"
    assert "scene_group" not in v1["global_vibe"]
    print("  v1.0 still passes Scene Contract (extra 2.3 fields stripped)")

    tmp = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
    tmp.write(json.dumps(handover, ensure_ascii=False) + "\n")
    tmp.close()
    loaded = load_jsonl(tmp.name)
    os.unlink(tmp.name)
    assert loaded[0]["image"] == "1014.jpg"

    batch_v1 = process_batch([yolo], [handover], [])
    batch_v23 = process_batch_v23([yolo], [handover])
    assert batch_v1[0]["entities"]
    assert batch_v23[0]["trigger_anchors"]

    _, _, _, visual_spec = load_mapping_config(REPO_ROOT / "configs" / "playback")
    allowed, _ = build_anchor_mapping(visual_spec)
    validate_record(batch_v23[0], allowed)
    print("  load_jsonl + process_batch + playback validate: ok")
    print("  PASS\n")


def main():
    print("=" * 60)
    print("ASMR-Creater Vision Layer - Full Test Suite")
    print("=" * 60)
    print()

    tests = [
        test_1_preprocessing,
        test_2_load_jsonl,
        test_3_entity_matching,
        test_4_merge_payload,
        test_5_process_batch,
        test_6_schema_validation,
        test_7_coordinate_mapping,
        test_8_vlm_format_normalization,
        test_9_exif_and_path_sanitize,
        test_10_v23_visual_record,
        test_11_handover_v23_input,
    ]

    passed = 0
    failed = 0
    for fn in tests:
        try:
            fn()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"\n  FAIL {fn.__name__}: {e}")
            import traceback; traceback.print_exc()

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed ({len(tests)} total)")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
