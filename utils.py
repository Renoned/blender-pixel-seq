"""工具函数模块"""

import numpy as np
from PIL import Image
from collections import Counter


def pixelate_image(image_array, pixel_size):
    """
    像素化图像

    Args:
        image_array: numpy 数组格式的图像
        pixel_size: 像素块大小

    Returns:
        像素化后的图像数组
    """
    height, width = image_array.shape[:2]
    channels = image_array.shape[2] if len(image_array.shape) > 2 else 1

    # 计算新的尺寸
    new_height = height // pixel_size
    new_width = width // pixel_size

    # 创建输出数组
    if channels >= 3:
        pixelated = np.zeros((new_height, new_width, channels), dtype=np.uint8)
    else:
        pixelated = np.zeros((new_height, new_width), dtype=np.uint8)

    for y in range(new_height):
        for x in range(new_width):
            # 获取像素块
            y_start = y * pixel_size
            y_end = min((y + 1) * pixel_size, height)
            x_start = x * pixel_size
            x_end = min((x + 1) * pixel_size, width)

            block = image_array[y_start:y_end, x_start:x_end]

            if channels == 4:  # RGBA
                # 忽略透明像素
                mask = block[:, :, 3] > 0
                if mask.any():
                    colors, counts = np.unique(
                        block[mask][:, :3], axis=0, return_counts=True
                    )
                    dominant_color = colors[counts.argmax()]
                    pixelated[y, x, :3] = dominant_color
                    pixelated[y, x, 3] = 255
                else:
                    pixelated[y, x] = [0, 0, 0, 0]
            elif channels == 3:  # RGB
                colors, counts = np.unique(
                    block.reshape(-1, block.shape[2]), axis=0, return_counts=True
                )
                dominant_color = colors[counts.argmax()]
                pixelated[y, x] = dominant_color
            else:  # 灰度
                pixelated[y, x] = np.mean(block).astype(np.uint8)

    return pixelated


def detect_noise_pixels(image_array, threshold=0.3):
    """
    检测噪点像素

    Args:
        image_array: numpy 数组格式的图像
        threshold: 噪点阈值 (0.0-1.0)

    Returns:
        噪点像素的坐标列表 [(y, x), ...]
    """
    height, width = image_array.shape[:2]
    channels = image_array.shape[2] if len(image_array.shape) > 2 else 1

    noise_pixels = []

    for y in range(1, height - 1):
        for x in range(1, width - 1):
            if channels == 4 and image_array[y, x, 3] == 0:
                continue  # 跳过透明像素

            # 获取当前像素
            if channels >= 3:
                current_pixel = image_array[y, x, :3]
            else:
                current_pixel = image_array[y, x]

            # 获取周围像素
            neighbors = []
            for dy in [-1, 0, 1]:
                for dx in [-1, 0, 1]:
                    if dy == 0 and dx == 0:
                        continue
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < height and 0 <= nx < width:
                        if channels == 4 and image_array[ny, nx, 3] == 0:
                            continue
                        if channels >= 3:
                            neighbor = image_array[ny, nx, :3]
                        else:
                            neighbor = image_array[ny, nx]
                        neighbors.append(neighbor)

            if not neighbors:
                continue

            # 计算当前像素与周围像素的差异
            neighbors = np.array(neighbors)
            differences = (
                np.linalg.norm(neighbors - current_pixel, axis=1)
                if channels >= 3
                else np.abs(neighbors - current_pixel)
            )

            # 如果当前像素与所有邻居都不同，可能是噪点
            if np.all(differences > threshold * 255):
                noise_pixels.append((y, x))

    return noise_pixels


def fix_noise_pixels(image_array, noise_pixels):
    """
    修复噪点像素

    Args:
        image_array: numpy 数组格式的图像
        noise_pixels: 噪点像素坐标列表

    Returns:
        修复后的图像数组
    """
    height, width = image_array.shape[:2]
    channels = image_array.shape[2] if len(image_array.shape) > 2 else 1

    denoised = image_array.copy()

    for y, x in noise_pixels:
        # 获取周围像素
        neighbors = []
        for dy in [-1, 0, 1]:
            for dx in [-1, 0, 1]:
                if dy == 0 and dx == 0:
                    continue
                ny, nx = y + dy, x + dx
                if 0 <= ny < height and 0 <= nx < width:
                    if channels == 4 and image_array[ny, nx, 3] == 0:
                        continue
                    if channels >= 3:
                        neighbor = image_array[ny, nx, :3]
                    else:
                        neighbor = image_array[ny, nx]
                    neighbors.append(neighbor)

        if neighbors:
            # 用周围像素的平均值替换
            neighbors = np.array(neighbors)
            if channels >= 3:
                denoised[y, x, :3] = np.mean(neighbors, axis=0).astype(np.uint8)
            else:
                denoised[y, x] = np.mean(neighbors).astype(np.uint8)

    return denoised


def color_quantization(image_array, max_colors=16):
    """
    颜色量化

    Args:
        image_array: numpy 数组格式的图像
        max_colors: 最大颜色数

    Returns:
        量化后的图像数组
    """
    from sklearn.cluster import KMeans

    height, width = image_array.shape[:2]
    channels = image_array.shape[2] if len(image_array.shape) > 2 else 1

    if channels < 3:
        return image_array

    # 重塑为像素列表
    pixels = image_array.reshape(-1, channels)

    if channels == 4:
        # 分离 RGB 和 Alpha
        rgb_pixels = pixels[:, :3]
        alpha_pixels = pixels[:, 3]

        # 只量化非透明像素
        mask = alpha_pixels > 0
        if not mask.any():
            return image_array

        rgb_to_quantize = rgb_pixels[mask]

        # KMeans 聚类
        kmeans = KMeans(
            n_clusters=min(max_colors, len(rgb_to_quantize)), random_state=0, n_init=10
        )
        kmeans.fit(rgb_to_quantize)

        # 替换颜色
        quantized_rgb = kmeans.cluster_centers_[kmeans.predict(rgb_to_quantize)]
        quantized_rgb = np.clip(quantized_rgb, 0, 255).astype(np.uint8)

        # 重建图像
        quantized_pixels = pixels.copy()
        quantized_pixels[mask, :3] = quantized_rgb
        quantized_image = quantized_pixels.reshape(height, width, channels)
    else:
        # KMeans 聚类
        kmeans = KMeans(
            n_clusters=min(max_colors, len(pixels)), random_state=0, n_init=10
        )
        kmeans.fit(pixels)

        # 替换颜色
        quantized_pixels = kmeans.cluster_centers_[kmeans.predict(pixels)]
        quantized_pixels = np.clip(quantized_pixels, 0, 255).astype(np.uint8)
        quantized_image = quantized_pixels.reshape(height, width, channels)

    return quantized_image


def apply_cell_shading(image_array, levels=4):
    """
    应用 Cell Shading 效果

    Args:
        image_array: numpy 数组格式的图像
        levels: 色阶数

    Returns:
        处理后的图像数组
    """
    height, width = image_array.shape[:2]
    channels = image_array.shape[2] if len(image_array.shape) > 2 else 1

    if channels < 3:
        return image_array

    shaded = image_array.copy()

    for y in range(height):
        for x in range(width):
            if channels == 4 and image_array[y, x, 3] == 0:
                continue

            # 获取 RGB 值
            rgb = image_array[y, x, :3].astype(np.float32)

            # 量化到指定色阶
            shaded_rgb = np.round(rgb / 255 * (levels - 1)) / (levels - 1) * 255
            shaded[y, x, :3] = np.clip(shaded_rgb, 0, 255).astype(np.uint8)

    return shaded
