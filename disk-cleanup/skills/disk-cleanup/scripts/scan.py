#!/usr/bin/env python3
"""
Read-only disk-cleanup scanner. Measures reclaimable space by category and tier.

This script NEVER deletes, moves, or modifies anything. It only walks known
cache / temp / trash / dev-cache locations and reports their sizes so a cleanup
plan can be built. Deletion is performed separately, per the SKILL.md, using
native tools where possible.

Cross-platform: macOS (Darwin), Linux, Windows.

Usage:
    python3 scan.py                 # scan OS cache/temp/trash + dev caches
    python3 scan.py --json          # machine-readable output
    python3 scan.py --projects ~/code ~/src   # also report Rust target/ and node_modules sizes
"""

import argparse
import json
import os
import platform
import shutil
import sys
from pathlib import Path

HOME = Path.home()
SYSTEM = platform.system()


# ---------------------------------------------------------------------------
# Size measurement (symlink / reparse-point safe, never follows links)
# ---------------------------------------------------------------------------

FILE_ATTRIBUTE_REPARSE_POINT = 0x400


def _is_reparse(path):
    """True if path is a Windows reparse point (junction / symlink)."""
    try:
        st = os.lstat(path)
    except OSError:
        return False
    attrs = getattr(st, "st_file_attributes", 0)
    return bool(attrs & FILE_ATTRIBUTE_REPARSE_POINT)


def dir_size(path):
    """Total bytes under path. Does not follow symlinks or reparse points,
    so it cannot wander out of the target directory into user data."""
    path = Path(path)
    try:
        if path.is_symlink() or _is_reparse(path):
            return 0
        if path.is_file():
            return path.stat().st_size
        if not path.is_dir():
            return 0
    except OSError:
        return 0

    total = 0
    for root, dirs, files in os.walk(path, topdown=True, followlinks=False,
                                     onerror=lambda e: None):
        # prune symlinked / reparse subdirectories so we never escape the tree
        pruned = []
        for d in dirs:
            full = os.path.join(root, d)
            if os.path.islink(full) or _is_reparse(full):
                continue
            pruned.append(d)
        dirs[:] = pruned
        for f in files:
            full = os.path.join(root, f)
            try:
                if os.path.islink(full):
                    continue
                total += os.path.getsize(full)
            except OSError:
                pass
    return total


def human(n):
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024.0 or unit == "TB":
            if unit == "B":
                return f"{int(n)} B"
            return f"{n:.1f} {unit}"
        n /= 1024.0


# ---------------------------------------------------------------------------
# Target catalog per OS
#
# Each entry: {"cat", "tier", "path", "additive"}
#   tier 0 = regenerates automatically, zero data loss
#   tier 1 = safe but irreversible (trash, old logs, device support)
#   tier 2 = opt-in: needs sudo/admin or expensive to rebuild
#   tier 3 = report only, never auto-delete
#   additive=False means the path is nested inside another listed path,
#   so it is shown for visibility but NOT summed into tier totals.
# ---------------------------------------------------------------------------

def _e(cat, tier, path, additive=True):
    return {"cat": cat, "tier": tier, "path": Path(path), "additive": additive}


def targets_darwin():
    L = HOME / "Library"
    dev = L / "Developer"
    return [
        _e("User caches", 0, L / "Caches"),
        _e("  Homebrew cache (within User caches)", 0, L / "Caches" / "Homebrew", additive=False),
        _e("  pip cache (within User caches)", 0, L / "Caches" / "pip", additive=False),
        _e("  Go build cache (within User caches)", 0, L / "Caches" / "go-build", additive=False),
        _e("Xcode DerivedData", 0, dev / "Xcode" / "DerivedData"),
        _e("npm cache", 0, HOME / ".npm" / "_cacache"),
        _e("Cargo registry cache", 0, HOME / ".cargo" / "registry" / "cache"),
        _e("Cargo registry src", 0, HOME / ".cargo" / "registry" / "src"),
        _e("User logs", 1, L / "Logs"),
        _e("Trash", 1, HOME / ".Trash"),
        _e("Xcode iOS DeviceSupport", 1, dev / "Xcode" / "iOS DeviceSupport"),
        _e("CoreSimulator caches", 1, dev / "CoreSimulator" / "Caches"),
        _e("Xcode Archives (review before deleting)", 3, dev / "Xcode" / "Archives"),
        _e("Go module cache (re-downloadable)", 3, HOME / "go" / "pkg" / "mod"),
    ]


def targets_linux():
    cache = HOME / ".cache"
    return [
        _e("User cache (XDG)", 0, cache),
        _e("  pip cache (within User cache)", 0, cache / "pip", additive=False),
        _e("  yarn cache (within User cache)", 0, cache / "yarn", additive=False),
        _e("  Go build cache (within User cache)", 0, cache / "go-build", additive=False),
        _e("  Thumbnails (within User cache)", 0, cache / "thumbnails", additive=False),
        _e("npm cache", 0, HOME / ".npm" / "_cacache"),
        _e("Cargo registry cache", 0, HOME / ".cargo" / "registry" / "cache"),
        _e("Cargo registry src", 0, HOME / ".cargo" / "registry" / "src"),
        _e("Trash", 1, HOME / ".local" / "share" / "Trash"),
        _e("Go module cache (re-downloadable)", 3, HOME / "go" / "pkg" / "mod"),
        # tier-2 system paths are reported but usually need sudo to clean; sizes
        # may read 0 without permission, which is expected.
        _e("APT cache (sudo)", 2, Path("/var/cache/apt/archives")),
        _e("systemd journal (sudo)", 2, Path("/var/log/journal")),
    ]


def targets_windows():
    local = Path(os.environ.get("LOCALAPPDATA", str(HOME / "AppData" / "Local")))
    appdata = Path(os.environ.get("APPDATA", str(HOME / "AppData" / "Roaming")))
    temp = Path(os.environ.get("TEMP", str(local / "Temp")))
    return [
        _e("User temp", 0, temp),
        _e("npm cache", 0, local / "npm-cache" / "_cacache"),
        _e("npm cache (roaming)", 0, appdata / "npm-cache" / "_cacache"),
        _e("pip cache", 0, local / "pip" / "Cache"),
        _e("Cargo registry cache", 0, HOME / ".cargo" / "registry" / "cache"),
        _e("Cargo registry src", 0, HOME / ".cargo" / "registry" / "src"),
        _e("Explorer thumbnail cache", 0, local / "Microsoft" / "Windows" / "Explorer"),
        _e("Windows temp (admin)", 2, Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Temp"),
    ]


def os_targets():
    if SYSTEM == "Darwin":
        return targets_darwin()
    if SYSTEM == "Linux":
        return targets_linux()
    if SYSTEM == "Windows":
        return targets_windows()
    return []


# ---------------------------------------------------------------------------
# Optional project-tree scan: Rust target/ and node_modules (report only)
# ---------------------------------------------------------------------------

PROJECT_SKIP = {".git", ".hg", ".svn", ".venv", "venv", ".direnv", "Library"}


def scan_projects(roots):
    rust, node = [], []
    for root in roots:
        root = Path(os.path.expanduser(str(root)))
        if not root.exists():
            continue
        for dirpath, dirs, _files in os.walk(root, topdown=True, followlinks=False,
                                              onerror=lambda e: None):
            base = os.path.basename(dirpath)
            if base == "target":
                parent = os.path.dirname(dirpath)
                looks_rust = (os.path.exists(os.path.join(parent, "Cargo.toml"))
                              or os.path.exists(os.path.join(dirpath, "CACHEDIR.TAG")))
                if looks_rust:
                    rust.append((dirpath, dir_size(dirpath)))
                    dirs[:] = []  # do not descend into a build dir we just measured
                    continue
            if base == "node_modules":
                node.append((dirpath, dir_size(dirpath)))
                dirs[:] = []
                continue
            dirs[:] = [d for d in dirs
                       if d not in PROJECT_SKIP
                       and not os.path.islink(os.path.join(dirpath, d))]
    rust.sort(key=lambda x: x[1], reverse=True)
    node.sort(key=lambda x: x[1], reverse=True)
    return rust, node


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def disk_usage_root():
    path = "/"
    if SYSTEM == "Windows":
        path = os.environ.get("SystemDrive", "C:") + "\\"
    try:
        return shutil.disk_usage(path), path
    except OSError:
        return None, path


def main():
    ap = argparse.ArgumentParser(description="Read-only disk cleanup scanner (no deletion).")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    ap.add_argument("--projects", nargs="*", default=None,
                    help="project roots to scan for Rust target/ and node_modules (report only)")
    args = ap.parse_args()

    entries = []
    for t in os_targets():
        if not t["path"].exists():
            continue
        size = dir_size(t["path"])
        entries.append({**t, "size": size, "path": str(t["path"])})
    entries.sort(key=lambda x: (x["tier"], -x["size"]))

    tier_totals = {0: 0, 1: 0, 2: 0, 3: 0}
    for e in entries:
        if e["additive"]:
            tier_totals[e["tier"]] += e["size"]

    rust, node = ([], [])
    if args.projects:
        rust, node = scan_projects(args.projects)

    du, du_path = disk_usage_root()

    if args.json:
        out = {
            "os": SYSTEM,
            "disk": ({"path": du_path, "total": du.total, "used": du.used, "free": du.free}
                     if du else None),
            "entries": entries,
            "tier_totals": tier_totals,
            "auto_reclaimable_tier0_1": tier_totals[0] + tier_totals[1],
            "optin_reclaimable_tier2": tier_totals[2],
            "projects": {
                "rust_target": [{"path": p, "size": s} for p, s in rust],
                "node_modules": [{"path": p, "size": s} for p, s in node],
            },
        }
        print(json.dumps(out, indent=2))
        return

    print(f"OS: {SYSTEM}")
    if du:
        print(f"Disk {du_path}: {human(du.free)} free of {human(du.total)} "
              f"({human(du.used)} used)")
    print()
    print(f"{'TIER':<5}{'SIZE':>11}  CATEGORY")
    print("-" * 64)
    for e in entries:
        marker = "" if e["additive"] else "  (info)"
        print(f"{e['tier']:<5}{human(e['size']):>11}  {e['cat']}{marker}")
        print(f"{'':>16}  {e['path']}")
    print("-" * 64)
    print(f"Tier 0 (auto, regenerates):      {human(tier_totals[0])}")
    print(f"Tier 1 (auto, irreversible):     {human(tier_totals[1])}")
    print(f"  -> safe auto reclaimable:      {human(tier_totals[0] + tier_totals[1])}")
    print(f"Tier 2 (opt-in, sudo/expensive): {human(tier_totals[2])}")

    if rust or node:
        print()
        print("Project build artifacts (REPORT ONLY, never auto-deleted):")
        if rust:
            rt = sum(s for _, s in rust)
            print(f"  Rust target/ dirs: {len(rust)}, {human(rt)} total")
            for p, s in rust[:10]:
                print(f"    {human(s):>11}  {p}")
        if node:
            nt = sum(s for _, s in node)
            print(f"  node_modules dirs: {len(node)}, {human(nt)} total")
            for p, s in node[:10]:
                print(f"    {human(s):>11}  {p}")


if __name__ == "__main__":
    sys.exit(main())
