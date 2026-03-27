# Blender Pixel Art Denoiser

一个用于创建死亡细胞风格像素艺术的 Blender 插件，支持批量渲染、像素化处理和噪点修复。

## 功能特性

- 🎨 **死亡细胞风格渲染** - 低分辨率 + 无抗锯齿 + Cell Shading
- 📦 **批量渲染** - 一次性处理时间轴所有帧
- 🖼️ **像素化处理** - 将高分辨率图像转换为像素艺术
- 🔧 **噪点修复** - 自动检测和修复孤立噪点像素
- 🎨 **颜色量化** - 限制调色板，增强像素艺术感

## 安装

### 方法 1：手动安装

1. 下载本仓库
2. 打开 Blender
3. 进入 `编辑` → `偏好设置` → `插件`
4. 点击 `安装...` 按钮
5. 选择下载的 `blender-pixel-art-denoiser` 文件夹
6. 启用插件

### 方法 2：复制到插件目录

将 `blender-pixel-art-denoiser` 文件夹复制到 Blender 插件目录：

- **Windows**: `%APPDATA%/Blender Foundation/Blender/[版本]/scripts/addons/`
- **macOS**: `~/Library/Application Support/Blender/[版本]/scripts/addons/`
- **Linux**: `~/.config/blender/[版本]/scripts/addons/`

## 使用方法

### 1. 渲染设置

1. 在 3D 视图侧边栏找到 `像素艺术` 标签
2. 设置渲染分辨率（建议 256x256 或更低）
3. 勾选 `关闭抗锯齿`
4. 点击 `应用渲染设置`

### 2. 批量渲染

1. 设置输出路径
2. 点击 `批量渲染` 按钮
3. 等待渲染完成

### 3. 像素化处理

1. 设置输入路径（渲染输出的文件夹）
2. 设置输出路径
3. 调整像素大小（推荐 2-8）
4. 点击 `像素化处理` 按钮

### 4. 噪点修复

1. 设置输入路径（像素化输出的文件夹）
2. 设置输出路径
3. 调整噪点阈值（推荐 0.2-0.4）
4. 点击 `噪点修复` 按钮

## 工作流程

```
Blender 场景
    ↓
批量渲染（关闭抗锯齿）
    ↓
像素化处理
    ↓
噪点修复
    ↓
导出 PNG 序列
```

## 依赖

- Blender 3.6+
- Python 3.10+（Blender 内置）
- PIL (Pillow)
- NumPy
- SciPy（可选，用于高级去噪）

### 安装依赖

在 Blender 的 Python 控制台中运行：

```python
import pip
pip.main(['install', 'pillow', 'numpy', 'scipy'])
```

或者在系统终端中：

```bash
pip install pillow numpy scipy
```

## 死亡细胞风格设置建议

### 渲染设置

- **分辨率**: 256x256 或更低
- **抗锯齿**: 关闭
- **渲染引擎**: Cycles（更真实）或 Eevee（更快）

### 材质设置

- 使用简单的颜色材质
- 避免复杂的纹理
- 使用 Cell Shading 效果

### 像素化设置

- **像素大小**: 2-4（根据需要调整）
- **颜色数**: 16-32 色

## 示例

### 原始渲染
![原始渲染](examples/original.png)

### 像素化后
![像素化](examples/pixelated.png)

### 噪点修复后
![去噪](examples/denoised.png)

## 常见问题

### Q: 像素化后图像太模糊怎么办？

A: 尝试以下方法：
1. 减小像素大小
2. 确保渲染时已关闭抗锯齿
3. 在 Blender 中使用 `滤镜大小 = 0`

### Q: 噪点太多怎么办？

A: 尝试以下方法：
1. 增加渲染采样数
2. 降低噪点阈值
3. 使用更好的光照设置

### Q: 如何获得死亡细胞风格？

A: 参考以下设置：
1. 低分辨率渲染（256x256）
2. 关闭抗锯齿
3. 使用简单的 Cell Shading 材质
4. 像素大小设置为 2-3
5. 导出后在 Aseprite 中微调

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License

## 致谢

- [pixfix](https://github.com/lovelaced/pixfix) - 像素艺术修复工具
- [Lospec Blender Toolkit](https://lospec.com/blender-toolkit/) - 像素艺术工具包
- [Dead Cells](https://dead-cells.com/) - 灵感来源
