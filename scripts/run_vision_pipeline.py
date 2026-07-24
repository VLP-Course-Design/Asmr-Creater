"""
run_vision_pipeline.py

项目主流程入口脚本 —— 步骤 1 图像预处理 + 步骤 2 YOLO 检测演示。

功能：
- 扫描指定文件夹内的所有图片
- 调用步骤 1 模块进行 Letterbox 预处理（640x640 + 224x224）
- 调用步骤 2 YOLO 检测器进行目标检测
- 打印内存中的数据结构，供人工复核

用法（仓库根目录下）:
    python scripts/run_vision_pipeline.py
"""

import os
import sys
from pathlib import Path

# 确保仓库根目录在 sys.path 中
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.vision.preprocess import get_image_files, batch_load_images
from src.vision.yolo import YoloDetector

# ════════════════════ 配置区域 ════════════════════
IMAGE_DIR = "./data/Val"              # 原始图片所在文件夹
TARGET_SIZE_YOLO = (640, 640)         # YOLO 目标尺寸
TARGET_SIZE_VLM = (224, 224)          # VLM 预留尺寸
SAVE_PROCESSED = True                 # 是否将处理后的图保存到硬盘
OUTPUT_DIR = "./processed_output"     # 处理后图片的输出文件夹
RUN_YOLO = True                       # 是否运行 YOLO 检测演示
# ═══════════════════════════════════════════════════


def main():
    print("=" * 60)
    print("🚀 ASMR 内容生成项目 - 步骤1+2：图像预处理与 YOLO 检测流水线")
    print("=" * 60)

    # 1. 检查原始文件夹是否存在
    if not os.path.exists(IMAGE_DIR):
        print(f"❌ 错误：原始图片文件夹 '{IMAGE_DIR}' 不存在，请检查路径。")
        print(f"   当前工作目录: {os.getcwd()}")
        return

    # 2. 获取所有图片路径（递归扫描）
    print(f"\n📂 正在扫描文件夹: {IMAGE_DIR}")
    image_paths = get_image_files(IMAGE_DIR, recursive=True)
    print(f"✅ 发现 {len(image_paths)} 张图片（jpg/jpeg/png）")

    if len(image_paths) == 0:
        print("⚠️ 没有找到任何图片，程序退出。")
        return

    # 3. 执行批量预处理
    print(f"\n🔄 开始批量预处理，目标尺寸 YOLO={TARGET_SIZE_YOLO}, VLM={TARGET_SIZE_VLM}")
    batch_results = batch_load_images(
        image_paths=image_paths,
        target_size_yolo=TARGET_SIZE_YOLO,
        target_size_vlm=TARGET_SIZE_VLM,
        verbose=True,
        save_dir=OUTPUT_DIR if SAVE_PROCESSED else None
    )

    # 4. 打印预处理结果摘要
    print("\n" + "=" * 60)
    print("📊 预处理完成，结果摘要：")
    print("=" * 60)
    print(f"  成功处理的图片数量: {len(batch_results)} / {len(image_paths)}")

    if not batch_results:
        print("⚠️ 没有图片被成功加载，请检查图片是否损坏。")
        return

    # 5. 打印内存中的数据结构
    sample = batch_results[0]
    print("\n📌 内存中的第一个数据字典结构：")
    for key, value in sample.items():
        if key in ('image', 'image_yolo', 'image_vlm'):
            print(f"  - '{key}': np.ndarray, 形状={value.shape}, 数据类型={value.dtype}")
        else:
            print(f"  - '{key}': {value}")

    # 6. 检查硬盘上的保存结果
    if SAVE_PROCESSED and os.path.exists(OUTPUT_DIR):
        saved_files = [f for f in os.listdir(OUTPUT_DIR)
                       if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        print(f"\n📁 处理后的图片已保存至: {OUTPUT_DIR}")
        print(f"   共保存 {len(saved_files)} 张 JPG 图片")
        if saved_files:
            print(f"   示例文件名: {saved_files[0]}")

    # 7. （可选）YOLO 检测演示
    if RUN_YOLO:
        print("\n" + "=" * 60)
        print("🔍 步骤 2 演示：YOLO 目标检测")
        print("=" * 60)
        try:
            detector = YoloDetector(
                model_name='yolo11n.pt',
                device='cpu',
                conf_threshold=0.25,
                iou_threshold=0.45
            )
            # 仅在少量图片上演示（避免耗时过长）
            demo_data = batch_results[:3]
            print(f"  对前 {len(demo_data)} 张图片执行检测演示...")
            detections = detector.detect(demo_data)

            for det_result in detections:
                img_name = os.path.basename(det_result.get("image_path", "?"))
                if det_result.get("error"):
                    print(f"  ❌ {img_name}: {det_result['error']}")
                else:
                    objs = det_result.get("detections", [])
                    print(f"  ✅ {img_name}: 检测到 {len(objs)} 个物体")
                    for obj in objs[:5]:  # 只显示前 5 个
                        print(f"       - {obj.name} "
                              f"(conf={obj.conf:.2f}, "
                              f"x={obj.x:.2f}, depth={obj.depth})")
        except Exception as e:
            print(f"  ⚠️ YOLO 检测演示跳过: {e}")

    print("\n" + "=" * 60)
    print("✅ 流水线执行完毕。")
    print("=" * 60)


if __name__ == "__main__":
    main()
