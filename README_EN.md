# Blender Pixel Art Denoiser

[![Release](https://img.shields.io/github/v/release/Renoned/blender-pixel-art-denoiser?sort=semver)](https://github.com/Renoned/blender-pixel-art-denoiser/releases)
[![Blender](https://img.shields.io/badge/Blender-3.6%2B-orange?logo=blender)](https://www.blender.org/)
[![License](https://img.shields.io/github/license/Renoned/blender-pixel-art-denoiser)](LICENSE)
[![Stars](https://img.shields.io/github/stars/Renoned/blender-pixel-art-denoiser?style=social)](https://github.com/Renoned/blender-pixel-art-denoiser)

A Blender addon for generating Dead Cells inspired pixel-art animation sequences from 3D scenes, with a focus on stable frame-to-frame output.

Chinese version: `README.md`

## Why This Addon

- Sequence rendering is harder than single-frame conversion.
- Typical issues include flicker, dark edge artifacts, random black pixels, and brightness drift.
- This addon is designed for a practical one-click pipeline for production-friendly sprite sequences.

## Features

- One-click timeline batch processing
- Toon material conversion for cleaner pixel-style shading
- Anti-alias cleanup for edge stability
- Color quantization with fallback strategy
- Optional 1px outline generation
- Preview and export directly in Blender

## Installation

### Option 1 (Recommended): Install from Releases

1. Open Releases: `https://github.com/Renoned/blender-pixel-art-denoiser/releases`
2. Download the latest package
3. Blender -> `Edit -> Preferences -> Add-ons -> Install...`
4. Select the zip and enable **Pixel Art Denoiser**

### Option 2: Install from source

Copy this project folder to:

- Windows: `%APPDATA%/Blender Foundation/Blender/<version>/scripts/addons/`
- macOS: `~/Library/Application Support/Blender/<version>/scripts/addons/`
- Linux: `~/.config/blender/<version>/scripts/addons/`

Then restart Blender or run `F3 -> Reload Scripts`.

## Quick Start

1. Open the addon panel in the 3D View sidebar (`像素艺术`).
2. Optional scene prep:
   - `一键生成标准像素光照`
   - `一键消除模型反光`
   - `一键材质转纯净赛璐璐 (保留颜色)`
3. Set output path and processing parameters.
4. Click `一键处理`.
5. Preview and export frames.

## Recommended Starter Settings

- Resolution: `256x256` (or lower)
- Disable anti-aliasing: enabled
- Pixel size: `3 ~ 5`
- Max colors: `12 ~ 24`
- Enable outline only when needed

## Dependencies

- Blender 3.6+
- Pillow
- NumPy
- scikit-learn (optional; Pillow fallback is built in)

```bash
pip install -r requirements.txt
```

## Roadmap

- [ ] Add sample assets and visual comparisons
- [ ] Add production presets for character/effects/background use cases
- [ ] Add advanced controls while keeping defaults simple

## Contributing

- Contribution guide: `CONTRIBUTING.md`
- Changelog: `CHANGELOG.md`

## License

MIT

## Acknowledgements

- [pixfix](https://github.com/lovelaced/pixfix)
- [Lospec Blender Toolkit](https://github.com/lospec/lospec-blender-toolkit)
- [Dead Cells](https://dead-cells.com/)
