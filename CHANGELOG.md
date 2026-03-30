# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

## [1.0.0] - 2026-03-30

### Added

- Added English documentation in `README_EN.md`.
- Added contribution guide in `CONTRIBUTING.md`.

### Changed

- Hardened processing pipeline to restore render settings reliably after batch processing.
- Improved compatibility for color quantization with fallback when `scikit-learn` is unavailable.
- Optimized outline and edge-gap handling logic for more robust frame processing.

### Fixed

- Reduced risk of unintended darkening when preserving Emission-driven materials.
- Limited outline gap-closing behavior to outline-enabled processing path.
