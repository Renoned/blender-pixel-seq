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
        name="最大颜色数", description="量化后的颜色数量", default=16, min=2, max=256
    )


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
    PIXELART_PT_main_panel,
    PIXELART_OT_apply_render_settings,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.pixelart_settings = PointerProperty(type=PixelArtSettings)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.pixelart_settings
