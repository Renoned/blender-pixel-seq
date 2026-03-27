# Blender Pixel Art Denoiser
# 一个用于创建死亡细胞风格像素艺术的 Blender 插件

bl_info = {
    "name": "Pixel Art Denoiser",
    "author": "trd32",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > Pixel Art",
    "description": "Create Dead Cells style pixel art with batch rendering and denoising",
    "warning": "",
    "doc_url": "",
    "category": "Render",
}

import bpy
from . import operators
from . import panels


def register():
    operators.register()
    panels.register()


def unregister():
    panels.unregister()
    operators.unregister()


if __name__ == "__main__":
    register()
