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
sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import cv2


def test_1_preprocessing():
    """预处理管线：Letterbox 形状、VLM 缩放、字段完整性"""
    print("=" * 50)
    print("Test 1: Preprocessing pipeline")
    print("=" * 50)

    from src.vision.preprocess import load_and_preprocess_image

    test_img = np.random.randint(0, 255, (300, 400, 3), dtype=np.uint8)
    test_path = str(REPO_ROOT / "_test_tmp.jpg")
    cv2.imwrite(test_path, cv2.cvtColor(test_img, cv2.COLOR_RGB2BGR))

    result = load_and_preprocess_image(test_path,
                                       target_size_yolo=(640, 640),
                                       target_size_vlm=(224, 224))
    assert result is not None, "load_and_preprocess_image returned None"
    assert result['image_yolo'].shape == (640, 640, 3)
    assert result['image_vlm'].shape == (224, 224, 3)
    for k in ['image', 'image_yolo', 'image_vlm', 'original_height',
              'original_width', 'scale', 'pad_left', 'pad_top',
              'new_width', 'new_height', 'path']:
        assert k in result, f"Missing field: {k}"
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

    from src.vision.vlm_yolo_fusion import load_jsonl

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

    from src.vision.vlm_yolo_fusion import _match_entity_to_yolo
    from src.vision.detector import Detection

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

    from src.vision.vlm_yolo_fusion import merge_structured_payload
    from src.vision.detector import Detection

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

    from src.vision.vlm_yolo_fusion import process_batch
    from src.vision.detector import Detection

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

    from src.vision.vlm_yolo_fusion import merge_structured_payload
    from src.vision.detector import Detection
    from src.common.contract import validate_scene

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

    from src.vision.yolo import YoloDetector

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

    from src.vision.vlm_yolo_fusion import merge_structured_payload

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
