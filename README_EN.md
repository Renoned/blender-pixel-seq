# Blender Pixel Art Denoiser

A Blender addon for generating Dead Cells inspired pixel-art frame sequences from 3D scenes. It focuses on stable batch output, anti-alias cleanup, color quantization, and optional outlines.

中文说明: `README.md`

## Features

- Dead Cells style rendering workflow (low resolution, hard shading, no AA)
- Batch processing across timeline frames
- Pixel-grid conversion with nearest-neighbor scaling
- Anti-alias cleanup for edge noise reduction
- Color quantization with robust fallback
- Optional 1px black outline generation
- One-click preview and export

## Requirements

- Blender 3.6+
- Python runtime bundled with Blender
- Pillow
- NumPy
- scikit-learn (optional; Pillow fallback is built in)

## Installation

### Option 1: Install as a Blender addon

1. Download this repository.
2. In Blender, open `Edit -> Preferences -> Add-ons`.
3. Click `Install...`.
4. Select the addon folder (or zip package).
5. Enable **Pixel Art Denoiser**.

### Option 2: Copy into addons directory

Copy the folder into your Blender addons path:

- Windows: `%APPDATA%/Blender Foundation/Blender/<version>/scripts/addons/`
- macOS: `~/Library/Application Support/Blender/<version>/scripts/addons/`
- Linux: `~/.config/blender/<version>/scripts/addons/`

Then reload scripts or restart Blender.

## Quick Start

1. Open the `像素艺术` tab in the 3D View sidebar.
2. (Optional) Run scene preprocess:
   - `一键生成标准像素光照`
   - `一键消除模型反光`
   - `一键材质转纯净赛璐璐 (保留颜色)`
3. Configure:
   - output path
   - render resolution (for example 256x256)
   - pixel size
   - denoise threshold
   - max colors
   - optional outline toggle
4. Click `一键处理`.
5. Click `预览效果`, then `输出图像`.

## Processing Pipeline

1. Batch render all timeline frames to temporary PNGs
2. Pixel-grid alignment (nearest-neighbor downscale + upscale)
3. Anti-alias cleanup
4. Brightness floor + color quantization
5. Optional outline gap close + outline generation
6. Export processed frames

## Notes

- The addon restores render settings after processing (resolution, file format, transparency, sampling, frame cursor).
- If `scikit-learn` is unavailable, quantization automatically falls back to Pillow so the pipeline still runs.
- For best style consistency, keep anti-aliasing disabled and use simple hard lighting.

## License

MIT

## Acknowledgements

- [pixfix](https://github.com/lovelaced/pixfix)
- [Lospec Blender Toolkit](https://lospec.com/blender-toolkit/)
- [Dead Cells](https://dead-cells.com/)
