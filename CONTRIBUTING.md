# Contributing

Thanks for your interest in improving Blender Pixel Art Denoiser.

## Before You Start

- Search existing issues before creating a new one.
- Keep changes focused; avoid mixing unrelated fixes.
- If your change affects output quality, include before/after examples.

## Development Setup

1. Fork and clone the repository.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy this addon folder into your Blender addons path.
4. In Blender, use `F3 -> Reload Scripts` after local code changes.

## Coding Guidelines

- Keep compatibility with Blender 3.6+.
- Prefer small, explicit changes with clear intent.
- Avoid introducing hard dependency requirements unless necessary.
- Preserve the current one-click workflow and existing UI behavior.
- Keep docs updated when user-facing behavior changes.

## Pull Request Checklist

- [ ] Code is focused and reviewed locally.
- [ ] `python -m py_compile __init__.py operators.py panels.py utils.py` passes.
- [ ] README/README_EN updated if behavior or UX changed.
- [ ] Changelog entry added or updated in `CHANGELOG.md`.
- [ ] Screenshots or short notes added for visual changes.

## Commit Message Style

Use concise, imperative commit messages. Examples:

- `fix edge outline dark pixel artifacts`
- `add English README for open-source release`
- `harden processing pipeline and improve compatibility`
