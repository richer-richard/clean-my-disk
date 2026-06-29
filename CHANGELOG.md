# Changelog

All notable changes to the `disk-cleanup` skill are documented here.
This project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.1] - 2026-06-29

### Fixed
- zsh portability: the per-OS delete commands now use
  `find <dir> -mindepth 1 -maxdepth 1 -exec rm -rf {} +` instead of `rm -rf <dir>/*`
  for Xcode DerivedData, Trash (macOS + Linux), the cargo registry fallback, and
  Xcode iOS DeviceSupport. A bare `<dir>/*` glob aborts with `no matches found`
  under zsh (the default macOS shell) when the directory is empty — and `2>/dev/null`
  cannot suppress that shell-level error. The `find` form is safe across bash/zsh
  and under `set -e`. Found by running the installed plugin end-to-end.

## [1.0.0] - 2026-06-29

### Added
- Initial release: cross-platform (macOS, Linux, Windows) disk-cleanup skill for
  Claude Code, distributed as a plugin via a self-hosted marketplace.
- Read-only scanner (`scripts/scan.py`, pure Python 3 stdlib) reporting reclaimable
  space by category and tier, with `--json` output and `--projects` sizing of Rust
  `target/` and `node_modules` (report-only). Symlink/reparse-point safe.
- Four-tier safety model (Tier 0 auto-regenerable, Tier 1 safe-irreversible,
  Tier 2 opt-in, Tier 3 report-only), nine hard safety rules, and a protected-path
  allowlist that overrides any autonomous/bypass instruction.
- Native-cleaner-first cleanup commands for macOS, Linux, and Windows, plus
  cross-platform Docker and Rust developer-cache guidance.
- `disk-cleanup-report.md` template with per-category bytes freed, skips, and a
  Tier 2 / Tier 3 menu of manual reclaim options.
