"""
image_preprocessor.py

图像预处理与批处理模块，为 YOLO 目标检测和 VLM 视觉语言模型提供标准化输入。
功能：
- 递归获取指定文件夹下的所有图像文件路径
- 统一读取图像并转换为 RGB 色彩空间
- Letterbox 保边缩放至目标尺寸（默认 640x640），灰色填充
- 批量加载与预处理，支持错误跳过和日志警告
- 返回包含图像数组、原始尺寸、缩放因子等信息的结构化数据
"""

import os
import cv2
import numpy as np
from typing import List, Dict, Optional, Tuple, Union

# 支持的图像格式
SUPPORTED_EXTENSIONS = ('.jpg', '.jpeg', '.png')


def get_image_files(root_dir: str, recursive: bool = True) -> List[str]:
    """
    获取指定目录下的所有图像文件路径。

    Args:
        root_dir: 根目录路径
        recursive: 是否递归遍历子目录，默认为 True

    Returns:
        图像文件路径列表（按字母排序）
    """
    image_paths = []
    if recursive:
        for dirpath, _, filenames in os.walk(root_dir):
            for fname in filenames:
                if fname.lower().endswith(SUPPORTED_EXTENSIONS):
                    image_paths.append(os.path.join(dirpath, fname))
    else:
        for fname in os.listdir(root_dir):
            if fname.lower().endswith(SUPPORTED_EXTENSIONS):
                image_paths.append(os.path.join(root_dir, fname))
    return sorted(image_paths)


def letterbox(
    img: np.ndarray,
    target_size: Tuple[int, int] = (640, 640),
    fill_color: Union[int, Tuple[int, int, int]] = (114, 114, 114)
) -> Tuple[np.ndarray, float, Tuple[int, int], Tuple[int, int]]:
    """
    对图像进行 Letterbox 保边缩放，用指定颜色填充剩余区域。

    Args:
        img: 输入图像 (H, W, C)，BGR 或 RGB 均可（但通常为 RGB）
        target_size: 目标尺寸 (width, height)，默认为 (640, 640)
        fill_color: 填充颜色，RGB 元组或灰度值，默认为灰色 (114,114,114)

    Returns:
        (resized_img, scale, (dw, dh), (pad_left, pad_top))
            - resized_img: 处理后的图像 (target_height, target_width, C)
            - scale: 实际缩放比例（用于坐标还原）
            - (dw, dh): 图像在填充前的宽、高（即缩放后的图像尺寸）
            - (pad_left, pad_top): 填充的左边距和上边距
    """
    target_w, target_h = target_size
    h, w = img.shape[:2]

    # 计算缩放比例（取较小比例，确保图像完全放入目标框）
    scale = min(target_w / w, target_h / h)
    new_w = int(w * scale)
    new_h = int(h * scale)

    # 等比缩放
    resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    # 创建目标尺寸的画布并填充
    if len(img.shape) == 3:
        canvas = np.full((target_h, target_w, img.shape[2]), fill_color, dtype=np.uint8)
    else:
        canvas = np.full((target_h, target_w), fill_color, dtype=np.uint8)

    # 计算填充偏移（居中放置）
    pad_left = (target_w - new_w) // 2
    pad_top = (target_h - new_h) // 2
    canvas[pad_top:pad_top + new_h, pad_left:pad_left + new_w] = resized

    return canvas, scale, (new_w, new_h), (pad_left, pad_top)


def load_and_preprocess_image(
    image_path: str,
    target_size: Tuple[int, int] = (640, 640)
) -> Optional[Dict]:
    """
    加载单张图像，转换为 RGB，执行 Letterbox 预处理，并返回相关信息。

    Args:
        image_path: 图像文件路径
        target_size: 目标尺寸 (width, height)

    Returns:
        成功时返回字典，包含：
            - 'image': 处理后的图像数组 (H, W, 3) uint8
            - 'original_height': 原始高度
            - 'original_width': 原始宽度
            - 'target_size': 目标尺寸 (width, height)
            - 'scale': 缩放比例
            - 'pad_left': 左填充像素数
            - 'pad_top': 上填充像素数
            - 'new_width': 缩放后的宽度（未填充前）
            - 'new_height': 缩放后的高度（未填充前）
            - 'path': 原始文件路径
        失败时返回 None
    """
    try:
        # 读取图像（OpenCV 默认为 BGR）
        img_bgr = cv2.imread(image_path)
        if img_bgr is None:
            raise ValueError(f"无法读取图像: {image_path}")

        # 转换为 RGB
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

        # 保存原始尺寸
        orig_h, orig_w = img_rgb.shape[:2]

        # Letterbox 预处理
        processed, scale, (new_w, new_h), (pad_left, pad_top) = letterbox(
            img_rgb, target_size
        )

        return {
            'image': processed,
            'original_height': orig_h,
            'original_width': orig_w,
            'target_size': target_size,
            'scale': scale,
            'pad_left': pad_left,
            'pad_top': pad_top,
            'new_width': new_w,
            'new_height': new_h,
            'path': image_path,
        }
    except Exception as e:
        print(f"Warning: 跳过文件 {image_path} - {e}")
        return None


def batch_load_images(
    image_paths: List[str],
    target_size: Tuple[int, int] = (640, 640),
    verbose: bool = True
) -> List[Dict]:
    """
    批量加载和预处理图像。

    Args:
        image_paths: 图像路径列表
        target_size: 目标尺寸 (width, height)
        verbose: 是否打印进度信息

    Returns:
        预处理结果列表，每个元素为 load_and_preprocess_image 返回的字典，
        已过滤掉加载失败（None）的条目。
    """
    results = []
    total = len(image_paths)
    for idx, path in enumerate(image_paths):
        if verbose and (idx % 100 == 0 or idx == total - 1):
            print(f"处理进度: {idx + 1}/{total}")
        result = load_and_preprocess_image(path, target_size)
        if result is not None:
            results.append(result)
    if verbose:
        print(f"批量预处理完成，成功加载 {len(results)}/{total} 张图像。")
    return results


def batch_load_images(
    image_paths: List[str],
    target_size: Tuple[int, int] = (640, 640),
    verbose: bool = True,
    save_dir: Optional[str] = None  # ⭐ 新增：保存路径，默认为 None 表示不保存
) -> List[Dict]:
    """
    批量加载和预处理图像。

    Args:
        image_paths: 图像路径列表
        target_size: 目标尺寸 (width, height)
        verbose: 是否打印进度信息
        save_dir: 可选，处理后图片的输出目录。若指定，自动创建文件夹并保存为 JPG 格式。

    Returns:
        预处理结果列表
    """
    # 如果指定了保存目录，提前创建（避免循环中重复判断）
    if save_dir:
        os.makedirs(save_dir, exist_ok=True)
        print(f"📁 处理后的图片将保存至: {save_dir}")

    results = []
    total = len(image_paths)
    for idx, path in enumerate(image_paths):
        if verbose and (idx % 100 == 0 or idx == total - 1):
            print(f"处理进度: {idx + 1}/{total}")

        result = load_and_preprocess_image(path, target_size)
        if result is not None:
            results.append(result)

            # ⭐ 新增保存逻辑：将内存中的数组存为硬盘文件
            if save_dir:
                try:
                    # 获取原文件名（不含后缀），拼接新后缀
                    base_name = os.path.splitext(os.path.basename(path))[0]
                    # 保存为 JPG，避免 PNG 体积过大，并加 _letterbox 标识
                    save_name = f"{base_name}_letterbox.jpg"
                    save_path = os.path.join(save_dir, save_name)

                    # 防重名：如果文件已存在，自动加数字后缀 (如 _1, _2)
                    counter = 1
                    original_path = save_path
                    while os.path.exists(save_path):
                        name_without_ext = f"{base_name}_letterbox_{counter}"
                        save_path = os.path.join(save_dir, f"{name_without_ext}.jpg")
                        counter += 1

                    # result['image'] 是 RGB，cv2.imwrite 需要 BGR 格式
                    cv2.imwrite(save_path, cv2.cvtColor(result['image'], cv2.COLOR_RGB2BGR))
                except Exception as e:
                    print(f"⚠️ 保存图片 {path} 时出错: {e}")

    if verbose:
        print(f"批量预处理完成，成功加载 {len(results)}/{total} 张图像。")
    return results
