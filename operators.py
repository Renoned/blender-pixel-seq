import bpy
import os
import glob
import tempfile
import numpy as np
from PIL import Image
from bpy.props import StringProperty, IntProperty, BoolProperty, FloatProperty
from bpy.types import Operator

# 临时目录
TEMP_DIR = os.path.join(tempfile.gettempdir(), "pixel_art_preview")


# ========== pixfix 核心算法 (Python 实现) ==========


def rgb_to_oklab(r, g, b):
    """RGB 转 OKLAB 色彩空间"""
    # 归一化到 0-1
    r, g, b = r / 255.0, g / 255.0, b / 255.0

    # 线性化
    lr = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    lg = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    lb = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b

    # 立方根
    lr = np.cbrt(lr)
    lg = np.cbrt(lg)
    lb = np.cbrt(lb)

    # OKLAB
    L = 0.2104542553 * lr + 0.7936177850 * lg - 0.0040720468 * lb
    a = 1.9779984951 * lr - 2.4285922050 * lg + 0.4505937099 * lb
    b = 0.0259040371 * lr + 0.7827717662 * lg - 0.8086757660 * lb

    return L, a, b


def oklab_distance(color1, color2):
    """计算两个颜色在 OKLAB 空间中的距离"""
    L1, a1, b1 = rgb_to_oklab(*color1[:3])
    L2, a2, b2 = rgb_to_oklab(*color2[:3])
    return np.sqrt((L2 - L1) ** 2 + (a2 - a1) ** 2 + (b2 - b1) ** 2)


def detect_grid_size(img_array, max_grid=32):
    """检测图像的像素网格大小"""
    height, width = img_array.shape[:2]
    best_score = 0
    best_size = 1

    for size in range(2, min(max_grid + 1, min(width, height) // 2)):
        # 计算边缘对齐分数
        score = 0
        count = 0

        # 检查水平边缘
        for y in range(0, height - 1, size):
            for x in range(width):
                if y + 1 < height:
                    diff = np.abs(
                        img_array[y, x].astype(int) - img_array[y + 1, x].astype(int)
                    )
                    score += np.sum(diff)
                    count += 1

        # 检查垂直边缘
        for y in range(height):
            for x in range(0, width - 1, size):
                if x + 1 < width:
                    diff = np.abs(
                        img_array[y, x].astype(int) - img_array[y, x + 1].astype(int)
                    )
                    score += np.sum(diff)
                    count += 1

        if count > 0:
            avg_score = score / count
            if avg_score > best_score:
                best_score = avg_score
                best_size = size

    return best_size


def remove_antialiasing(img_array, threshold=0.3):
    """移除抗锯齿效果"""
    height, width = img_array.shape[:2]
    channels = img_array.shape[2] if len(img_array.shape) > 2 else 1

    if channels < 3:
        return img_array

    result = img_array.copy()

    for y in range(1, height - 1):
        for x in range(1, width - 1):
            if channels == 4 and img_array[y, x, 3] == 0:
                continue

            current = img_array[y, x, :3]

            # 获取 8 个邻居
            neighbors = []
            for dy in [-1, 0, 1]:
                for dx in [-1, 0, 1]:
                    if dy == 0 and dx == 0:
                        continue
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < height and 0 <= nx < width:
                        if channels == 4 and img_array[ny, nx, 3] == 0:
                            continue
                        neighbors.append(img_array[ny, nx, :3])

            if len(neighbors) < 2:
                continue

            # 找到两个主要颜色
            neighbors = np.array(neighbors)

            # 计算当前像素与邻居的距离
            distances = []
            for n in neighbors:
                dist = oklab_distance(current, n)
                distances.append(dist)

            # 如果当前像素与所有邻居都"介于"两者之间，可能是抗锯齿
            min_dist = min(distances)
            if min_dist > threshold:
                # 找到最近的邻居
                closest_idx = np.argmin(distances)
                result[y, x, :3] = neighbors[closest_idx]

    return result


def remove_dark_artifacts(img_array):
    """移除模型边缘因降采样产生的异常黑色/暗灰色像素斑块"""
    height, width = img_array.shape[:2]
    channels = img_array.shape[2] if len(img_array.shape) > 2 else 1
    if channels < 4:
        return img_array

    result = img_array.copy()

    for y in range(1, height - 1):
        for x in range(1, width - 1):
            if img_array[y, x, 3] == 0:
                continue

            r, g, b = img_array[y, x, :3]
            # 极暗像素检测 (亮度 < 40)
            luminance = 0.299 * r + 0.587 * g + 0.114 * b

            if luminance < 40:
                # 检查四周是否有透明背景 (意味着它是边缘像素)
                is_edge = (
                    img_array[y - 1, x, 3] == 0
                    or img_array[y + 1, x, 3] == 0
                    or img_array[y, x - 1, 3] == 0
                    or img_array[y, x + 1, 3] == 0
                )

                # 如果是边缘的暗色像素，很可能是 Alpha 预乘的伪影
                # 用周围最亮的非透明颜色替换它
                if is_edge:
                    brightest_color = None
                    max_lum = -1

                    for dy in [-1, 0, 1]:
                        for dx in [-1, 0, 1]:
                            if dy == 0 and dx == 0:
                                continue
                            ny, nx = y + dy, x + dx

                            if img_array[ny, nx, 3] > 0:
                                nr, ng, nb = img_array[ny, nx, :3]
                                n_lum = 0.299 * nr + 0.587 * ng + 0.114 * nb
                                if n_lum > max_lum and n_lum > 40:
                                    max_lum = n_lum
                                    brightest_color = tuple(img_array[ny, nx, :3])

                    if brightest_color is not None:
                        result[y, x, :3] = brightest_color

    return result


def remove_isolated_pixels(img_array):
    """众数滤波器 (Mode Filter)：移除孤立的噪点像素，使色块更纯净"""
    height, width = img_array.shape[:2]
    channels = img_array.shape[2] if len(img_array.shape) > 2 else 1
    if channels < 3:
        return img_array

    result = img_array.copy()

    # 将图像转换为更快的整数视图来进行比较
    img_view = (
        img_array.view(dtype=np.uint32).reshape(height, width)
        if channels == 4
        else img_array
    )

    for y in range(1, height - 1):
        for x in range(1, width - 1):
            if channels == 4 and img_array[y, x, 3] == 0:
                continue

            # 收集周围 8 个邻居的颜色
            neighbors = []
            for dy in [-1, 0, 1]:
                for dx in [-1, 0, 1]:
                    if dy == 0 and dx == 0:
                        continue
                    ny, nx = y + dy, x + dx
                    if channels == 4 and img_array[ny, nx, 3] == 0:
                        continue
                    neighbors.append(tuple(img_array[ny, nx, :3]))

            if not neighbors:
                continue

            # 计算出现频率最高的颜色
            from collections import Counter

            counts = Counter(neighbors)
            most_common_color, max_count = counts.most_common(1)[0]
            current_color = tuple(img_array[y, x, :3])

            # 【优化】降低触发条件：
            # 只有当这个像素周围**一个同色都没有**(绝对孤立)，或者被某种颜色**高度包围**(>=6个)时，才会被同化。
            # 这样可以保留那些有意设计的 2px 细线和像素画本身的细节。
            if counts.get(current_color, 0) == 0 or max_count >= 6:
                result[y, x, :3] = most_common_color

    return result


def clamp_minimum_brightness(img_array, min_luminance=35):
    """
    亮度托底：防止物体本身的暗部颜色（如深棕色皮带）被 KMeans 算法吞噬成纯黑色。
    它会将所有非全透明非绝对纯黑（非外描边）的像素亮度提升到指定的下限。
    """
    height, width = img_array.shape[:2]
    channels = img_array.shape[2] if len(img_array.shape) > 2 else 1
    if channels < 3:
        return img_array

    result = img_array.copy()

    # 将图像转换为浮点进行计算
    float_img = result.astype(np.float32)
    r, g, b = float_img[:, :, 0], float_img[:, :, 1], float_img[:, :, 2]

    # 计算当前亮度
    luminance = 0.299 * r + 0.587 * g + 0.114 * b

    # 找到亮度低于最低阈值的像素（但排除纯黑 0，因为纯黑可能是故意的背景或极暗缝隙）
    mask = (luminance < min_luminance) & (luminance > 0)

    if channels == 4:
        # 只处理非透明像素
        mask = mask & (img_array[:, :, 3] > 0)

    # 提高亮度：用乘数提升 RGB
    if np.any(mask):
        # 计算需要提升的倍数，加个极小值防除零
        multiplier = min_luminance / (luminance[mask] + 0.001)

        # 为了防止偏色，最大放大倍数限制为 3 倍
        multiplier = np.clip(multiplier, 1.0, 3.0)

        float_img[mask, 0] = np.clip(r[mask] * multiplier, 0, 255)
        float_img[mask, 1] = np.clip(g[mask] * multiplier, 0, 255)
        float_img[mask, 2] = np.clip(b[mask] * multiplier, 0, 255)

        result[:, :, :3] = float_img[:, :, :3].astype(np.uint8)

    return result


def quantize_colors(img_array, max_colors=16):
    """颜色量化"""
    from sklearn.cluster import KMeans

    height, width = img_array.shape[:2]
    channels = img_array.shape[2] if len(img_array.shape) > 2 else 1

    if channels < 3:
        return img_array

    # 重塑为像素列表
    pixels = img_array.reshape(-1, channels)

    if channels == 4:
        # 分离 RGB 和 Alpha
        rgb_pixels = pixels[:, :3].astype(np.float64)
        alpha_pixels = pixels[:, 3]

        # 只量化非透明像素
        mask = alpha_pixels > 0
        if not mask.any():
            return img_array

        rgb_to_quantize = rgb_pixels[mask]

        # KMeans 聚类
        n_clusters = min(max_colors, len(rgb_to_quantize))
        kmeans = KMeans(n_clusters=n_clusters, random_state=0, n_init="auto")
        kmeans.fit(rgb_to_quantize)

        # 获取聚类标签
        labels = kmeans.predict(rgb_to_quantize)

        # 用聚类中心替换颜色
        quantized_rgb = kmeans.cluster_centers_[labels]
        quantized_rgb = np.clip(quantized_rgb, 0, 255).astype(np.uint8)

        # 重建图像
        quantized_pixels = pixels.copy()
        quantized_pixels[mask, :3] = quantized_rgb
        quantized_image = quantized_pixels.reshape(height, width, channels)
    else:
        # KMeans 聚类
        pixels_float = pixels.astype(np.float64)
        n_clusters = min(max_colors, len(pixels_float))
        kmeans = KMeans(n_clusters=n_clusters, random_state=0, n_init="auto")
        kmeans.fit(pixels_float)

        # 获取聚类标签
        labels = kmeans.predict(pixels_float)

        # 用聚类中心替换颜色
        quantized_pixels = kmeans.cluster_centers_[labels]
        quantized_pixels = np.clip(quantized_pixels, 0, 255).astype(np.uint8)
        quantized_image = quantized_pixels.reshape(height, width, channels)

    return quantized_image


def apply_pixel_outline(img_array, outline_color=(0, 0, 0)):
    """在图像的 Alpha 透明边界生成一圈干净的 1px 描边"""
    height, width = img_array.shape[:2]
    channels = img_array.shape[2] if len(img_array.shape) > 2 else 1
    if channels != 4:
        return img_array

    result = img_array.copy()
    for y in range(height):
        for x in range(width):
            if img_array[y, x, 3] > 0:  # 如果是实体像素
                # 检查四周是否有透明像素
                is_edge = False
                if y == 0 or y == height - 1 or x == 0 or x == width - 1:
                    is_edge = True
                else:
                    if (
                        img_array[y - 1, x, 3] == 0
                        or img_array[y + 1, x, 3] == 0
                        or img_array[y, x - 1, 3] == 0
                        or img_array[y, x + 1, 3] == 0
                    ):
                        is_edge = True
                if is_edge:
                    result[y, x, :3] = outline_color
    return result


def close_outline_gaps(img_array):
    """仅对透明边缘附近的黑线做 1px 闭运算，补齐断续描边"""
    height, width = img_array.shape[:2]
    channels = img_array.shape[2] if len(img_array.shape) > 2 else 1
    if channels != 4:
        return img_array

    result = img_array.copy()
    rgb = result[:, :, :3]

    alpha_mask = result[:, :, 3] > 0

    # 只在透明边缘附近进行补线，避免把角色内部深色区域误补成黑色
    edge_mask = np.zeros((height, width), dtype=bool)
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            if not alpha_mask[y, x]:
                continue
            if not np.all(alpha_mask[y - 1 : y + 2, x - 1 : x + 2]):
                edge_mask[y, x] = True

    # 黑线判定阈值（收紧阈值，减少额外黑像素）
    black_mask = (rgb[:, :, 0] < 22) & (rgb[:, :, 1] < 22) & (rgb[:, :, 2] < 22)
    black_mask = black_mask & alpha_mask & edge_mask

    # 3x3 膨胀
    dilated = np.zeros_like(black_mask)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            y_src_start = max(0, -dy)
            y_src_end = height - max(0, dy)
            x_src_start = max(0, -dx)
            x_src_end = width - max(0, dx)

            y_dst_start = max(0, dy)
            y_dst_end = height - max(0, -dy)
            x_dst_start = max(0, dx)
            x_dst_end = width - max(0, -dx)

            dilated[y_dst_start:y_dst_end, x_dst_start:x_dst_end] |= black_mask[
                y_src_start:y_src_end, x_src_start:x_src_end
            ]

    # 3x3 腐蚀（闭运算完成）
    closed = np.ones_like(dilated)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            y_src_start = max(0, -dy)
            y_src_end = height - max(0, dy)
            x_src_start = max(0, -dx)
            x_src_end = width - max(0, dx)

            y_dst_start = max(0, dy)
            y_dst_end = height - max(0, -dy)
            x_dst_start = max(0, dx)
            x_dst_end = width - max(0, -dx)

            closed[y_dst_start:y_dst_end, x_dst_start:x_dst_end] &= dilated[
                y_src_start:y_src_end, x_src_start:x_src_end
            ]

    # 仅补“原本不是黑线”的缺口，避免整条线变粗
    fill_mask = closed & (~black_mask) & edge_mask
    result[fill_mask, :3] = np.array([0, 0, 0], dtype=np.uint8)
    return result


def snap_to_grid(img_array, grid_size):
    """将像素对齐到网格，同时过滤掉会导致黑边的半透明边缘像素"""
    height, width = img_array.shape[:2]
    channels = img_array.shape[2] if len(img_array.shape) > 2 else 1

    new_height = height // grid_size
    new_width = width // grid_size

    if channels >= 3:
        result = np.zeros((new_height, new_width, channels), dtype=np.uint8)
    else:
        result = np.zeros((new_height, new_width), dtype=np.uint8)

    for y in range(new_height):
        for x in range(new_width):
            y_start = y * grid_size
            y_end = min((y + 1) * grid_size, height)
            x_start = x * grid_size
            x_end = min((x + 1) * grid_size, width)

            block = img_array[y_start:y_end, x_start:x_end]

            if channels == 4:  # RGBA
                # 【防黑边核心】过滤掉 Alpha 低于 250 的半透明像素
                # 这能过滤掉 Eevee 边缘与黑色背景混合产生的脏像素
                mask = block[:, :, 3] >= 250
                if mask.any():
                    # 过滤掉极暗的边缘像素 (防预乘 Alpha 黑边)
                    valid_pixels = block[mask]
                    luminance = (
                        0.299 * valid_pixels[:, 0]
                        + 0.587 * valid_pixels[:, 1]
                        + 0.114 * valid_pixels[:, 2]
                    )

                    # 如果不是所有的像素都是黑色，就过滤掉那些因为 alpha 混合而变得极暗的伪像素
                    if len(valid_pixels) > 1 and np.max(luminance) > 20:
                        brightness_mask = luminance > 20
                        if brightness_mask.any():
                            valid_pixels = valid_pixels[brightness_mask]

                    colors, counts = np.unique(
                        valid_pixels[:, :3], axis=0, return_counts=True
                    )
                    dominant_color = colors[counts.argmax()]
                    result[y, x, :3] = dominant_color
                    result[y, x, 3] = 255
                else:
                    result[y, x] = [0, 0, 0, 0]
            elif channels == 3:  # RGB
                colors, counts = np.unique(
                    block.reshape(-1, block.shape[2]), axis=0, return_counts=True
                )
                dominant_color = colors[counts.argmax()]
                result[y, x] = dominant_color
            else:  # 灰度
                result[y, x] = np.mean(block).astype(np.uint8)

    return result


# ========== Blender 操作符 ==========


class PIXELART_OT_flatten_materials(Operator):
    """一键将所有材质的高光降为0，粗糙度拉满，从物理上防止噪点产生"""

    bl_idname = "pixelart.flatten_materials"
    bl_label = "一键消除模型反光 (去噪点)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        count = 0
        for mat in bpy.data.materials:
            if mat.use_nodes and mat.node_tree:
                for node in mat.node_tree.nodes:
                    if node.type == "BSDF_PRINCIPLED":
                        # 1. 粗糙度拉满 (变哑光)
                        if "Roughness" in node.inputs:
                            node.inputs["Roughness"].default_value = 1.0

                        # 2. 消除高光 (兼容 Blender 4.x 和旧版本)
                        if "Specular IOR Level" in node.inputs:
                            node.inputs["Specular IOR Level"].default_value = 0.0
                        if "Specular" in node.inputs:
                            node.inputs["Specular"].default_value = 0.0

                        # 3. 消除金属感 (金属会产生强烈的黑白对比噪点)
                        if "Metallic" in node.inputs:
                            node.inputs["Metallic"].default_value = 0.0

                        # 4. 消除清漆反光
                        if "Coat Weight" in node.inputs:
                            node.inputs["Coat Weight"].default_value = 0.0
                        if "Clearcoat" in node.inputs:
                            node.inputs["Clearcoat"].default_value = 0.0

                        count += 1

        self.report({"INFO"}, f"已成功优化 {count} 个材质！(可按 Ctrl+Z 撤销)")
        return {"FINISHED"}


# 内部拜耳矩阵图像生成器
def get_bayer_image():
    img_name = "bayer_matrix_4x4"
    if img_name in bpy.data.images:
        return bpy.data.images[img_name]

    # 4x4 Bayer 矩阵数据，归一化到 0-1
    bayer_matrix = (
        np.array(
            [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]],
            dtype=np.float32,
        )
        / 16.0
    )

    img = bpy.data.images.new(
        img_name, width=4, height=4, alpha=False, float_buffer=True
    )
    pixels = np.zeros((4, 4, 4), dtype=np.float32)
    # 反转Y轴因为Blender图像坐标从左下角开始
    for y in range(4):
        for x in range(4):
            val = bayer_matrix[3 - y, x]
            pixels[y, x] = [val, val, val, 1.0]

    img.pixels = pixels.flatten()
    return img


class PIXELART_OT_convert_toon_shader(Operator):
    """保留原始贴图颜色的赛璐璐材质转换器（MULTIPLY 方案）"""

    bl_idname = "pixelart.convert_toon_shader"
    bl_label = "一键材质转纯净赛璐璐 (保留颜色)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        count = 0

        def collect_upstream(node, keep_nodes):
            for inp in node.inputs:
                if inp.is_linked:
                    src = inp.links[0].from_node
                    if src not in keep_nodes:
                        keep_nodes.add(src)
                        collect_upstream(src, keep_nodes)

        for mat in bpy.data.materials:
            if not mat.use_nodes or not mat.node_tree:
                continue

            nodes = mat.node_tree.nodes
            links = mat.node_tree.links

            output_node = None
            for node in nodes:
                if node.type == "OUTPUT_MATERIAL":
                    output_node = node
                    break
            if not output_node:
                continue

            # AI 模型常见：Surface 直接由 Emission 驱动。
            # 这类材质若强行重建，容易出现“白膜”观感；先走保守路径。
            surface_input = output_node.inputs.get("Surface")
            if surface_input and surface_input.is_linked:
                surface_src = surface_input.links[0].from_node
                if surface_src.type == "EMISSION":
                    # 保留原始 Emission 材质，不在这里改强度，避免“整体变暗”
                    count += 1
                    continue

            source_color_node = None
            source_color_value = (0.8, 0.8, 0.8, 1.0)

            # 优先使用原始贴图节点，避免重复转换时把“旧的处理链”当作新输入，导致白膜叠加
            for node in nodes:
                if node.type == "TEX_IMAGE":
                    source_color_node = node
                    break

            # 如果没有贴图，再从当前输出链逆向提取颜色源
            if source_color_node is None:
                surface_input = output_node.inputs.get("Surface")
                if surface_input and surface_input.is_linked:
                    surface_src = surface_input.links[0].from_node
                    if surface_src.type == "EMISSION":
                        color_input = surface_src.inputs.get("Color")
                        if color_input:
                            if color_input.is_linked:
                                source_color_node = color_input.links[0].from_node
                            elif hasattr(color_input, "default_value"):
                                source_color_value = tuple(color_input.default_value)
                    elif surface_src.type == "BSDF_PRINCIPLED":
                        base_input = surface_src.inputs.get("Base Color")
                        if base_input:
                            if base_input.is_linked:
                                source_color_node = base_input.links[0].from_node
                            elif hasattr(base_input, "default_value"):
                                source_color_value = tuple(base_input.default_value)

            # ========== 第二步：清理旧节点，只保留输出和颜色源链路 ==========
            nodes_to_keep = {output_node}
            if source_color_node:
                nodes_to_keep.add(source_color_node)
                collect_upstream(source_color_node, nodes_to_keep)

            for node in list(nodes):
                if node not in nodes_to_keep:
                    nodes.remove(node)

            # ========== 第三步：构建极简赛璐璐光照（禁用发光叠加，防白膜） ==========

            # 1. 光照捕捉
            diffuse_bsdf = nodes.new(type="ShaderNodeBsdfDiffuse")
            diffuse_bsdf.location = (-800, -200)
            diffuse_bsdf.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
            diffuse_bsdf.inputs["Roughness"].default_value = 1.0

            shader_to_rgb = nodes.new(type="ShaderNodeShaderToRGB")
            shader_to_rgb.location = (-500, -200)
            links.new(diffuse_bsdf.outputs["BSDF"], shader_to_rgb.inputs["Shader"])

            # 2. 赛璐璐光照阶梯：仅做轻微分层，避免覆盖原贴图
            color_ramp_light = nodes.new(type="ShaderNodeValToRGB")
            color_ramp_light.location = (-200, -200)
            color_ramp_light.color_ramp.interpolation = "CONSTANT"
            color_ramp_light.color_ramp.elements[0].position = 0.0
            color_ramp_light.color_ramp.elements[0].color = (0.90, 0.90, 0.90, 1.0)
            color_ramp_light.color_ramp.elements.new(0.55)
            color_ramp_light.color_ramp.elements[1].color = (0.97, 0.97, 0.97, 1.0)
            color_ramp_light.color_ramp.elements.new(0.82)
            color_ramp_light.color_ramp.elements[2].color = (1.0, 1.0, 1.0, 1.0)
            links.new(shader_to_rgb.outputs["Color"], color_ramp_light.inputs["Fac"])

            # 3. 原始颜色 × 赛璐璐光照 = 被照亮的主体
            mix_color = nodes.new(type="ShaderNodeMix")
            mix_color.location = (100, -100)
            mix_color.data_type = "RGBA"
            mix_color.blend_type = "MULTIPLY"
            mix_color.inputs[0].default_value = 1.0

            if source_color_node:
                src_out = (
                    source_color_node.outputs.get("Color")
                    or source_color_node.outputs[0]
                )
                links.new(src_out, mix_color.inputs[6])
            else:
                mix_color.inputs[6].default_value = source_color_value

            links.new(color_ramp_light.outputs["Color"], mix_color.inputs[7])

            # 4. 输出（不做额外发光叠加，彻底避免白膜）
            emission_node = nodes.new(type="ShaderNodeEmission")
            emission_node.location = (320, -80)
            links.new(mix_color.outputs[2], emission_node.inputs["Color"])
            if "Strength" in emission_node.inputs:
                emission_node.inputs["Strength"].default_value = 1.0

            # 5. 连接到材质输出
            if output_node:
                links.new(
                    emission_node.outputs["Emission"], output_node.inputs["Surface"]
                )

            count += 1

        self.report({"INFO"}, f"成功将 {count} 个材质转为纯净赛璐璐 (保留原始颜色)")
        return {"FINISHED"}


class PIXELART_OT_one_click_process(Operator):
    """一键处理：渲染 + 像素化 + 去噪（仅预览）"""

    bl_idname = "pixelart.one_click_process"
    bl_label = "一键处理"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        settings = scene.pixelart_settings

        # 创建临时目录
        os.makedirs(TEMP_DIR, exist_ok=True)

        # ========== 步骤 1: 批量渲染到临时目录 ==========
        self.report({"INFO"}, "步骤 1/4: 批量渲染...")

        # 保存原始设置
        original_filepath = scene.render.filepath
        original_filter_size = scene.render.filter_size
        original_film_transparent = scene.render.film_transparent

        # 尝试保存 Eevee 采样设置 (Blender 4.2 Eevee-Next)
        original_eevee_samples = None
        try:
            if hasattr(scene, "eevee") and hasattr(scene.eevee, "taa_render_samples"):
                original_eevee_samples = scene.eevee.taa_render_samples
        except:
            pass

        # 应用渲染设置
        scene.render.resolution_x = settings.render_resolution_x
        scene.render.resolution_y = settings.render_resolution_y

        if settings.disable_antialiasing:
            scene.render.filter_size = 0.0
            # 【杀手锏】强制将 Eevee 渲染采样设为 1。
            # 这是 Blender 产生边缘黑灰色杂边的罪魁祸首！(多采样会导致边缘像素和透明底进行混合)
            try:
                if hasattr(scene, "eevee") and hasattr(
                    scene.eevee, "taa_render_samples"
                ):
                    scene.eevee.taa_render_samples = 1
            except:
                pass
        else:
            scene.render.filter_size = 1.5

        # 设置渲染输出格式
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGBA"
        # 【极其关键】强制开启透明背景！否则边缘会和灰黑色的世界背景融合，产生无法消除的黑边！
        scene.render.film_transparent = True

        # 批量渲染
        frame_count = scene.frame_end - scene.frame_start + 1
        for frame in range(scene.frame_start, scene.frame_end + 1):
            scene.frame_set(frame)
            scene.render.filepath = os.path.join(TEMP_DIR, f"frame_{frame:04d}")
            bpy.ops.render.render(write_still=True)

        # 恢复原始设置
        scene.render.filepath = original_filepath
        scene.render.filter_size = original_filter_size
        scene.render.film_transparent = original_film_transparent
        try:
            if original_eevee_samples is not None and hasattr(scene, "eevee"):
                scene.eevee.taa_render_samples = original_eevee_samples
        except:
            pass

        self.report({"INFO"}, f"渲染完成: {frame_count} 帧")

        # ========== 步骤 2: 网格对齐 ==========
        self.report({"INFO"}, "步骤 2/4: 网格对齐...")

        png_files = sorted(glob.glob(os.path.join(TEMP_DIR, "frame_*.png")))
        grid_size = settings.pixel_size

        for png_file in png_files:
            img = Image.open(png_file)

            # 【重要修复】废弃容易导致发光点丢失的 Mode Filter 数组运算！
            # 采用原生 NEAREST 重采样，可以绝对保护极亮像素和线条，并真正实现等比例网格化！
            width, height = img.size
            new_w = width // grid_size
            new_h = height // grid_size

            if new_w > 0 and new_h > 0:
                # 先缩小，再放大，实现完美的马赛克网格，不损失任何特征像素！
                # PIL.Image.NEAREST 等价于 0，是最原生的像素暴力采样
                small_img = img.resize((new_w, new_h), resample=0)
                pixelated_img = small_img.resize((width, height), resample=0)
                pixelated_img.save(png_file)

        self.report({"INFO"}, f"网格对齐完成: {len(png_files)} 张")

        # ========== 步骤 3: 移除抗锯齿 ==========
        self.report({"INFO"}, "步骤 3/4: 移除抗锯齿...")

        for png_file in png_files:
            img = Image.open(png_file)
            img_array = np.array(img)

            # 移除抗锯齿
            aa_removed = remove_antialiasing(
                img_array, threshold=settings.denoise_threshold
            )

            # 保存
            Image.fromarray(aa_removed).save(png_file)

        self.report({"INFO"}, f"抗锯齿移除完成: {len(png_files)} 张")

        # ========== 步骤 4: 颜色量化 ==========

        self.report({"INFO"}, "步骤 4/4: 颜色量化...")

        max_colors = settings.max_colors
        for png_file in png_files:
            img = Image.open(png_file)
            img_array = np.array(img)

            # 亮度托底：温和提亮，避免整体发灰发暗
            clamped = clamp_minimum_brightness(img_array, min_luminance=36)

            # 颜色量化
            quantized = quantize_colors(clamped, max_colors=max_colors)

            # 保存
            Image.fromarray(quantized).save(png_file)

        self.report({"INFO"}, f"颜色量化完成: {len(png_files)} 张")

        # ========== 步骤 4.5: 边框补线（闭运算） ==========
        # 仅在开启外描边时执行，避免把“正常深色区域”误补成黑像素
        if settings.enable_outline:
            self.report({"INFO"}, "步骤 4.5/5: 边框补线...")
            for png_file in png_files:
                img = Image.open(png_file)
                img_array = np.array(img)
                closed = close_outline_gaps(img_array)
                Image.fromarray(closed).save(png_file)

        # ========== 步骤 5: 可选描边 ==========
        if settings.enable_outline:
            self.report({"INFO"}, "步骤 5/5: 生成外描边...")
            for png_file in png_files:
                img = Image.open(png_file)
                img_array = np.array(img)
                outlined = apply_pixel_outline(img_array)
                Image.fromarray(outlined).save(png_file)

        self.report({"INFO"}, "处理完成！点击「预览效果」查看")
        return {"FINISHED"}


class PIXELART_OT_preview_result(Operator):
    """预览处理结果"""

    bl_idname = "pixelart.preview_result"
    bl_label = "预览效果"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        # 检查临时目录
        if not os.path.exists(TEMP_DIR):
            self.report({"WARNING"}, "请先执行「一键处理」")
            return {"CANCELLED"}

        png_files = sorted(glob.glob(os.path.join(TEMP_DIR, "*.png")))
        if not png_files:
            self.report({"WARNING"}, "请先执行「一键处理」")
            return {"CANCELLED"}

        # 加载第一帧
        first_frame = png_files[0]
        img_name = "pixelart_preview"

        # 强制移除旧的缓存，确保加载的是最新处理的图像
        if img_name in bpy.data.images:
            bpy.data.images.remove(bpy.data.images[img_name])

        img = bpy.data.images.load(first_frame)
        img.name = img_name

        # 打开一个新窗口来专门显示处理后的图片，而不是使用 F11 (F11 永远只显示原始的 Render Result)
        bpy.ops.wm.window_new()

        # 获取新创建的窗口 (通常是最后一个)
        new_window = context.window_manager.windows[-1]

        # 将新窗口的区域设置为图像编辑器，并指定我们要预览的图片
        for area in new_window.screen.areas:
            area.type = "IMAGE_EDITOR"
            # 寻找该区域的图像编辑器空间
            for space in area.spaces:
                if space.type == "IMAGE_EDITOR":
                    space.image = img

        self.report({"INFO"}, f"已在新窗口预览处理结果: {len(png_files)} 帧")
        return {"FINISHED"}


class PIXELART_OT_export_images(Operator):
    """导出处理后的图像"""

    bl_idname = "pixelart.export_images"
    bl_label = "输出图像"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        import shutil

        # 检查临时目录
        if not os.path.exists(TEMP_DIR):
            self.report({"WARNING"}, "请先执行「一键处理」")
            return {"CANCELLED"}

        png_files = sorted(glob.glob(os.path.join(TEMP_DIR, "*.png")))
        if not png_files:
            self.report({"WARNING"}, "请先执行「一键处理」")
            return {"CANCELLED"}

        scene = context.scene
        settings = scene.pixelart_settings

        # 创建输出目录
        base_dir = bpy.path.abspath(settings.output_path)
        denoised_dir = os.path.join(base_dir, "denoised")
        os.makedirs(denoised_dir, exist_ok=True)

        # 复制文件到输出目录
        for png_file in png_files:
            dst = os.path.join(denoised_dir, os.path.basename(png_file))
            shutil.copy2(png_file, dst)

        self.report({"INFO"}, f"已导出 {len(png_files)} 张到: {denoised_dir}")
        return {"FINISHED"}


class PIXELART_OT_open_output_folder(Operator):
    """打开输出文件夹"""

    bl_idname = "pixelart.open_output_folder"
    bl_label = "打开输出文件夹"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        import subprocess
        import sys

        scene = context.scene
        settings = scene.pixelart_settings
        base_dir = bpy.path.abspath(settings.output_path)

        # 根据系统打开文件夹
        if sys.platform == "win32":
            os.startfile(base_dir)
        elif sys.platform == "darwin":
            subprocess.run(["open", base_dir])
        else:
            subprocess.run(["xdg-open", base_dir])

        self.report({"INFO"}, f"已打开: {base_dir}")
        return {"FINISHED"}


class PIXELART_OT_setup_pixel_lighting(Operator):
    """删除杂乱光源，建立单一日光，适合像素画的纯净阴影"""

    bl_idname = "pixelart.setup_pixel_lighting"
    bl_label = "一键生成标准像素光照"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        import math

        # 1. 使用底层 API 删除光源，避免 bpy.ops 导致的上下文错误 (Context Incorrect)
        lights_to_delete = [obj for obj in context.scene.objects if obj.type == "LIGHT"]
        count = len(lights_to_delete)
        for obj in lights_to_delete:
            bpy.data.objects.remove(obj, do_unlink=True)

        # 2. 使用底层 API 添加一盏强力且阴影锐利的平行光 (Sun)
        light_data = bpy.data.lights.new(name="PixelArt_Sun_Data", type="SUN")
        light_data.energy = 2.0  # 保证足够的亮度让 Toon Shader 亮部显现
        light_data.angle = 0.0  # 【核心】太阳光角度设为0，产生绝对锐利的硬阴影

        light_obj = bpy.data.objects.new(name="PixelArt_Sun", object_data=light_data)
        context.collection.objects.link(light_obj)  # 链接到当前集合

        # 旋转角度设置为经典的 45 度角
        light_obj.location = (0, 0, 5)
        light_obj.rotation_euler = (math.radians(45), 0, math.radians(45))

        self.report(
            {"INFO"}, f"已清理 {count} 个杂乱光源，并生成了适合像素画的硬阴影平行光！"
        )
        return {"FINISHED"}


classes = (
    PIXELART_OT_setup_pixel_lighting,
    PIXELART_OT_flatten_materials,
    PIXELART_OT_convert_toon_shader,
    PIXELART_OT_one_click_process,
    PIXELART_OT_preview_result,
    PIXELART_OT_export_images,
    PIXELART_OT_open_output_folder,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
