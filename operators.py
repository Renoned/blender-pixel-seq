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


def snap_to_grid(img_array, grid_size):
    """将像素对齐到网格"""
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
                mask = block[:, :, 3] > 0
                if mask.any():
                    colors, counts = np.unique(
                        block[mask][:, :3], axis=0, return_counts=True
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
    """参考 Lucas Roedel 开源像素插件重写的纯净赛璐璐材质转换器"""

    bl_idname = "pixelart.convert_toon_shader"
    bl_label = "一键材质转纯净赛璐璐 (无渐变)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        count = 0

        for mat in bpy.data.materials:
            if not mat.use_nodes or not mat.node_tree:
                continue

            nodes = mat.node_tree.nodes
            links = mat.node_tree.links

            # 寻找 Principled BSDF
            principled = None
            for node in nodes:
                if node.type == "BSDF_PRINCIPLED":
                    principled = node
                    break

            if not principled:
                continue

            # ========== 【关键修复1】提取原始贴图信息，然后彻底清除旧节点 ==========
            # 之前的代码从未清理旧节点，每次点击都会叠加新节点，导致旧的 Principled BSDF
            # 依然连接着输出，它的高光/金属/AO 产生的黑色信号依然会被渲染出来！
            base_color_input = principled.inputs.get("Base Color")

            # 保存原始贴图节点（如果有的话）
            original_tex_node = None
            original_color_value = (0.8, 0.8, 0.8, 1.0)
            if base_color_input:
                original_color_value = tuple(base_color_input.default_value)
                if base_color_input.is_linked:
                    from_node = base_color_input.links[0].from_node
                    # 保护贴图节点不被删除
                    original_tex_node = from_node

            # 找到输出节点（保护它不被删除）
            output_node = None
            for node in nodes:
                if node.type == "OUTPUT_MATERIAL":
                    output_node = node
                    break

            # 删除所有旧节点（除了输出节点和贴图节点）
            nodes_to_keep = {output_node}
            if original_tex_node:
                nodes_to_keep.add(original_tex_node)
                # 如果贴图节点有上游节点（比如 UV Map），也要保留
                for inp in original_tex_node.inputs:
                    if inp.is_linked:
                        nodes_to_keep.add(inp.links[0].from_node)

            for node in list(nodes):
                if node not in nodes_to_keep:
                    nodes.remove(node)

            # ========== 【关键修复2】参考 Lucas Roedel 开源插件，从零构建纯净节点树 ==========
            # 核心原理: Principled BSDF -> ShaderToRGB -> ColorRamp(CONSTANT) -> Emission
            # 这是被 Lucas Roedel、Mezaka 等多位像素艺术大师验证过的标准管线。
            # 关键: 不再创建额外的 Diffuse，直接把 Principled BSDF 的完整光照信息
            # 通过 ShaderToRGB 捕获，然后用 ColorRamp 硬截断。

            # 1. 新建一个干净的 Principled BSDF（替代原来那个被污染的）
            new_bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
            new_bsdf.location = (-600, 0)
            # 强制消除所有产生噪点的属性
            new_bsdf.inputs["Roughness"].default_value = 1.0
            if "Specular IOR Level" in new_bsdf.inputs:
                new_bsdf.inputs["Specular IOR Level"].default_value = 0.0
            if "Specular" in new_bsdf.inputs:
                new_bsdf.inputs["Specular"].default_value = 0.0
            new_bsdf.inputs["Metallic"].default_value = 0.0
            if "Coat Weight" in new_bsdf.inputs:
                new_bsdf.inputs["Coat Weight"].default_value = 0.0

            # 连接原始贴图或设置原始颜色
            if original_tex_node:
                # 找到贴图节点的 Color 输出
                tex_color_output = (
                    original_tex_node.outputs.get("Color")
                    or original_tex_node.outputs[0]
                )
                links.new(tex_color_output, new_bsdf.inputs["Base Color"])
            else:
                new_bsdf.inputs["Base Color"].default_value = original_color_value

            # 2. Shader to RGB（捕获完整的光照信息，含贴图颜色）
            shader_to_rgb = nodes.new(type="ShaderNodeShaderToRGB")
            shader_to_rgb.location = (-300, 0)
            links.new(new_bsdf.outputs["BSDF"], shader_to_rgb.inputs["Shader"])

            # 3. ColorRamp（CONSTANT 硬截断，这是消灭黑色噪点的核心！）
            # 参考 Lucas Roedel 的做法：用 CONSTANT 插值把连续的光照
            # 强制量化成 3 个纯净的色阶。
            # 【关键区别】这里 ColorRamp 直接处理的是带颜色的光照结果，
            # 不是灰度值！所以输出就是最终颜色，不需要再做任何乘法或混合！
            color_ramp = nodes.new(type="ShaderNodeValToRGB")
            color_ramp.location = (-50, 0)
            color_ramp.color_ramp.interpolation = "CONSTANT"
            # 3 个色阶: 暗部从 0.0 开始, 中间从 0.35, 亮部从 0.65
            color_ramp.color_ramp.elements[0].position = 0.0
            color_ramp.color_ramp.elements[0].color = (
                0.65,
                0.65,
                0.65,
                1.0,
            )  # 暗部不会低于 65% 亮度
            color_ramp.color_ramp.elements.new(0.35)
            color_ramp.color_ramp.elements[1].color = (0.85, 0.85, 0.85, 1.0)  # 中间调
            color_ramp.color_ramp.elements.new(0.65)
            color_ramp.color_ramp.elements[2].color = (1.0, 1.0, 1.0, 1.0)  # 亮部
            links.new(shader_to_rgb.outputs["Color"], color_ramp.inputs["Fac"])

            # 4. Emission（自发光输出，防止二次光照污染）
            emission_node = nodes.new(type="ShaderNodeEmission")
            emission_node.location = (200, 0)
            links.new(color_ramp.outputs["Color"], emission_node.inputs["Color"])

            # 5. 连接到输出
            if output_node:
                links.new(
                    emission_node.outputs["Emission"], output_node.inputs["Surface"]
                )

            count += 1

        self.report({"INFO"}, f"成功将 {count} 个材质转为纯净赛璐璐 (已清理旧节点)")
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
            img_array = np.array(img)

            # 对齐到网格
            snapped = snap_to_grid(img_array, grid_size)

            # 保存
            Image.fromarray(snapped).save(png_file)

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

        # ========== 步骤 3.5: 孤立噪点去除 (Despeckle) ==========
        self.report({"INFO"}, "步骤: 移除孤立噪点...")
        for png_file in png_files:
            img = Image.open(png_file)
            img_array = np.array(img)
            despeckled = remove_isolated_pixels(img_array)
            Image.fromarray(despeckled).save(png_file)

        # ========== 步骤 4: 颜色量化 ==========

        self.report({"INFO"}, "步骤 4/4: 颜色量化...")

        max_colors = settings.max_colors
        for png_file in png_files:
            img = Image.open(png_file)
            img_array = np.array(img)

            # 颜色量化
            quantized = quantize_colors(img_array, max_colors=max_colors)

            # 保存
            Image.fromarray(quantized).save(png_file)

        self.report({"INFO"}, f"颜色量化完成: {len(png_files)} 张")

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
