import bpy
import os
from bpy.types import Panel, PropertyGroup, Operator
from bpy.props import (
    StringProperty,
    IntProperty,
    BoolProperty,
    FloatProperty,
    PointerProperty,
)


class PixelArtSettings(PropertyGroup):
    """像素艺术设置"""

    # 输出路径
    output_path: StringProperty(
        name="输出路径",
        description="所有文件保存到这个文件夹（自动创建子目录）",
        default="//pixel_art_output/",
        subtype="DIR_PATH",
    )

    # 渲染设置
    disable_antialiasing: BoolProperty(
        name="关闭抗锯齿", description="渲染时关闭抗锯齿", default=True
    )

    render_resolution_x: IntProperty(
        name="渲染分辨率 X", description="渲染分辨率宽度", default=256, min=1, max=4096
    )

    render_resolution_y: IntProperty(
        name="渲染分辨率 Y", description="渲染分辨率高度", default=256, min=1, max=4096
    )

    # 像素化设置
    pixel_size: IntProperty(
        name="像素大小", description="每个像素块的大小", default=4, min=1, max=32
    )

    # 去噪设置
    denoise_threshold: FloatProperty(
        name="抗锯齿阈值",
        description="移除抗锯齿的灵敏度",
        default=0.3,
        min=0.0,
        max=1.0,
    )

    # 颜色量化设置
    max_colors: IntProperty(
        name="最大颜色数", description="量化后的颜色数量", default=15, min=2, max=256
    )

    enable_outline: BoolProperty(
        name="生成纯正像素外描边",
        description="在透明边缘生成一圈绝对纯净的1像素黑色描边",
        default=False,
    )


import json


def get_settings_file():
    return os.path.join(os.path.dirname(__file__), "settings.json")


def load_settings():
    file_path = get_settings_file()
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_settings(settings_dict):
    try:
        with open(get_settings_file(), "w", encoding="utf-8") as f:
            json.dump(settings_dict, f, indent=4)
    except Exception:
        pass


class PIXELART_OT_save_preset(Operator):
    """保存当前设置为默认预设"""

    bl_idname = "pixelart.save_preset"
    bl_label = "保存为默认预设"

    def execute(self, context):
        settings = context.scene.pixelart_settings
        settings_dict = {
            "output_path": settings.output_path,
            "disable_antialiasing": settings.disable_antialiasing,
            "render_resolution_x": settings.render_resolution_x,
            "render_resolution_y": settings.render_resolution_y,
            "pixel_size": settings.pixel_size,
            "denoise_threshold": settings.denoise_threshold,
            "max_colors": settings.max_colors,
            "enable_outline": settings.enable_outline,
        }
        save_settings(settings_dict)
        self.report({"INFO"}, "预设已保存！下次打开Blender将自动加载。")
        return {"FINISHED"}


class PIXELART_OT_load_preset(Operator):
    """加载保存的预设"""

    bl_idname = "pixelart.load_preset"
    bl_label = "加载预设"

    def execute(self, context):
        settings = context.scene.pixelart_settings
        saved = load_settings()
        if saved:
            if "output_path" in saved:
                settings.output_path = saved["output_path"]
            if "disable_antialiasing" in saved:
                settings.disable_antialiasing = saved["disable_antialiasing"]
            if "render_resolution_x" in saved:
                settings.render_resolution_x = saved["render_resolution_x"]
            if "render_resolution_y" in saved:
                settings.render_resolution_y = saved["render_resolution_y"]
            if "pixel_size" in saved:
                settings.pixel_size = saved["pixel_size"]
            if "denoise_threshold" in saved:
                settings.denoise_threshold = saved["denoise_threshold"]
            if "max_colors" in saved:
                settings.max_colors = saved["max_colors"]
            if "enable_outline" in saved:
                settings.enable_outline = saved["enable_outline"]
            self.report({"INFO"}, "预设已加载！")
        else:
            self.report({"WARNING"}, "未找到保存的预设！")
        return {"FINISHED"}


class PIXELART_PT_main_panel(Panel):
    """像素艺术主面板"""

    bl_label = "像素艺术去噪器"
    bl_idname = "PIXELART_PT_main_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "像素艺术"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.pixelart_settings

        # 输出路径
        box = layout.box()
        box.label(text="输出设置", icon="FILE_FOLDER")
        row = box.row()
        row.prop(settings, "output_path")

        # 渲染设置
        box = layout.box()
        box.label(text="渲染设置", icon="RENDER_STILL")

        row = box.row()
        row.prop(settings, "disable_antialiasing")

        row = box.row()
        row.prop(settings, "render_resolution_x")
        row.prop(settings, "render_resolution_y")

        row = box.row()
        row.operator("pixelart.apply_render_settings", icon="PREFERENCES")

        # 像素化设置
        box = layout.box()
        box.label(text="像素化设置", icon="IMAGE_DATA")
        row = box.row()
        row.prop(settings, "pixel_size")

        # 去噪设置
        box = layout.box()
        box.label(text="去噪设置", icon="BRUSH_DATA")
        row = box.row()
        row.prop(settings, "denoise_threshold")
        row = box.row()
        row.prop(settings, "max_colors")
        row = box.row()
        row.prop(settings, "enable_outline")

        # 预设管理
        box = layout.box()
        box.label(text="预设管理", icon="PRESET")
        row = box.row(align=True)
        row.operator("pixelart.save_preset", icon="FILE_TICK")
        row.operator("pixelart.load_preset", icon="FILE_REFRESH")

        # 场景与材质预处理
        box = layout.box()
        box.label(text="场景与材质预处理", icon="SCENE_DATA")

        row = box.row()
        row.scale_y = 1.2
        row.operator("pixelart.setup_pixel_lighting", icon="LIGHT_SUN")

        row = box.row()
        row.scale_y = 1.2
        row.operator("pixelart.flatten_materials", icon="SHADING_RENDERED")
        row = box.row()
        row.scale_y = 1.2
        row.operator("pixelart.convert_toon_shader", icon="SHADING_TEXTURE")

        # 一键处理
        box = layout.box()
        box.label(text="一键处理", icon="PLAY")
        row = box.row()
        row.scale_y = 2.0
        row.operator("pixelart.one_click_process", icon="RENDER_ANIMATION")

        # 预览
        box = layout.box()
        box.label(text="预览效果", icon="IMAGE_DATA")
        row = box.row()
        row.operator("pixelart.preview_result", icon="ZOOM_IN")
        row = box.row()
        row.operator("pixelart.export_images", icon="EXPORT")
        row = box.row()
        row.operator("pixelart.open_output_folder", icon="FILE_FOLDER")


class PIXELART_OT_apply_render_settings(Operator):
    """应用渲染设置"""

    bl_idname = "pixelart.apply_render_settings"
    bl_label = "应用渲染设置"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        settings = scene.pixelart_settings

        # 应用分辨率设置
        scene.render.resolution_x = settings.render_resolution_x
        scene.render.resolution_y = settings.render_resolution_y

        # 应用抗锯齿设置
        if settings.disable_antialiasing:
            scene.render.filter_size = 0.0  # 关闭抗锯齿
        else:
            scene.render.filter_size = 1.5  # 默认值

        self.report({"INFO"}, "渲染设置已应用")
        return {"FINISHED"}


classes = (
    PixelArtSettings,
    PIXELART_OT_save_preset,
    PIXELART_OT_load_preset,
    PIXELART_PT_main_panel,
    PIXELART_OT_apply_render_settings,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.pixelart_settings = PointerProperty(type=PixelArtSettings)

    # 延迟加载设置，因为场景可能还没完全初始化
    def load_initial_settings():
        saved = load_settings()
        if saved and bpy.context.scene:
            try:
                settings = bpy.context.scene.pixelart_settings
                if "output_path" in saved:
                    settings.output_path = saved["output_path"]
                if "disable_antialiasing" in saved:
                    settings.disable_antialiasing = saved["disable_antialiasing"]
                if "render_resolution_x" in saved:
                    settings.render_resolution_x = saved["render_resolution_x"]
                if "render_resolution_y" in saved:
                    settings.render_resolution_y = saved["render_resolution_y"]
                if "pixel_size" in saved:
                    settings.pixel_size = saved["pixel_size"]
                if "denoise_threshold" in saved:
                    settings.denoise_threshold = saved["denoise_threshold"]
                if "max_colors" in saved:
                    settings.max_colors = saved["max_colors"]
                if "enable_outline" in saved:
                    settings.enable_outline = saved["enable_outline"]
            except Exception:
                pass
        return None

    bpy.app.timers.register(load_initial_settings, first_interval=1.0)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.pixelart_settings
