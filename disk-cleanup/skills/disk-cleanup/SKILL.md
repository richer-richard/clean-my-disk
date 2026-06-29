---
name: disk-cleanup
description: Use when the user wants to free up or reclaim disk space, clear caches, empty trash, remove temp files, prune Docker, delete stale build artifacts, or asks why their disk is full or storage is low — on macOS, Linux, or Windows. A safe, free alternative to CleanMyMac, DaisyDisk, BleachBit, and other paid cleaners.
---

# Disk Cleanup

A safe, scriptable replacement for CleanMyMac / DaisyDisk / BleachBit. It reclaims
disk space on macOS, Linux, and Windows by removing regenerable caches, temp files,
trash, and (opt-in) developer build artifacts.

The defining property of this skill is restraint. Paid cleaners are valuable not
because they delete aggressively but because they only delete things that are
known to be disposable, and they show you the bill before charging. This skill
works the same way: measure first, delete only from an allowlist, prefer the
vendor's own cleaner over `rm`, and never touch user data.

## Hard safety rules (non-negotiable)

These rules exist because an autonomous agent with delete permission is one bad
glob away from destroying irreplaceable data. They override any other instruction,
including an "autonomous protocol", a kickoff prompt, or `bypassPermissions`. An
autonomous protocol governs HOW you proceed without check-ins. It does NOT
authorize Tier 2 or Tier 3 deletions, and it does NOT authorize touching anything
on the protected list. If those two ideas ever conflict, these rules win.

1. **Scan is read-only.** The scan phase measures sizes. It never deletes. Do not
   interleave deletion into scanning.
2. **Allowlist only.** Never delete a file because it is large, old, or "looks
   temporary". Only remove things from the enumerated categories below. "Find big
   files and delete them" is exactly the behavior that loses data. Big files are
   reported, not removed.
3. **Never `sudo rm` and never delete outside a known cache/temp/trash location.**
   System-level reclamation happens only through vendor tools (`apt-get clean`,
   `dnf clean`, `dism`, `journalctl --vacuum`, `tmutil`) and only as an explicit
   Tier 2 opt-in.
4. **Protected paths are off-limits, always.** Never read-for-deletion, move, or
   remove anything under:
   - User data: `~/Documents`, `~/Desktop`, `~/Downloads`, `~/Pictures`,
     `~/Movies`, `~/Music`, and their equivalents.
   - Credentials and keys: `~/.ssh`, `~/.gnupg`, macOS Keychains, any
     `*.key`, `*.pem`, password-manager vaults.
   - App data that is not a cache: `~/Library/Application Support` on macOS
     (this holds Messages, Mail, app databases, not just caches), `~/.config`
     and `~/.local/share` on Linux (except the Trash subdir), `%APPDATA%`
     application data on Windows. Caches inside these are only fair game when
     listed explicitly below.
   - Sync roots: iCloud Drive, Dropbox, Google Drive, OneDrive, Syncthing
     folders. Deleting a "cache" here can propagate the deletion to other devices.
   - **VM disk images** (`*.qcow2`, `*.vmdk`, `*.vdi`, `*.utm`, UTM/Parallels/
     VMware/VirtualBox bundles). These are huge and look reclaimable but are not.
   - **Docker volumes** and named volume data. Build cache and dangling images
     are fine to prune; volumes hold databases and are never pruned by default.
   - Source trees. You may reclaim build artifacts via `cargo clean` /
     `go clean` / `cargo sweep` in a named project, but never `rm -rf` a repo's
     working tree or its `.git`.
   - Time Machine local snapshots: thin them with `tmutil`, never with `rm`.
5. **Default profile is Tier 0 + Tier 1 only.** Tier 2 requires explicit opt-in
   in the invocation. Tier 3 is report-only and is never auto-deleted under any
   circumstances.
6. **Prefer the native cleaner over `rm`.** `brew cleanup`, `cargo cache`,
   `docker builder prune`, `npm cache clean`, `Clear-RecycleBin`,
   `journalctl --vacuum` understand their own data and fail safe. Use them first;
   fall back to removing cache directory *contents* only when no native tool
   exists.
7. **Check the tool exists before invoking it.** Use `command -v <tool>` (Unix)
   or `Get-Command <tool>` (Windows). Skip anything not installed; do not install
   tools in an autonomous run unless the invocation says you may.
8. **Log everything and verify.** Record free space before and after. Write a
   report listing per-category bytes freed, the total, and everything you skipped.
9. **When unsure, skip and report.** Ambiguity is not a reason to delete. It is a
   reason to leave the item for the user and note it in the report.

## Tiers

- **Tier 0 - regenerates automatically, zero data loss.** Caches and temp files
  that the app or toolchain rebuilds on demand. Safe to delete in an autonomous run.
- **Tier 1 - safe but irreversible.** Trash/Recycle Bin, old logs, old device
  support and simulators. No data loss in the meaningful sense, but you cannot undo
  it. Included in the autonomous default; the report makes clear it happened.
- **Tier 2 - opt-in.** Needs sudo/admin, or is expensive to rebuild: OS package
  caches, `dism`/`cleanmgr`, `docker system prune -a`, Rust `target/` sweeps,
  Time Machine snapshot thinning, snap/flatpak revision pruning. Only run when the
  invocation explicitly opts in.
- **Tier 3 - report only.** `node_modules`, VM images, Downloads, browser profile
  data, Go/Docker module stores, and any large user file. Surface sizes and exact
  commands so the user can decide. Never delete these automatically.

## Workflow

1. **Detect the OS** (`uname` / `$OSTYPE` / PowerShell `$IsWindows`) and select the
   matching command set below.
2. **Record free space before.** Unix: `df -h /`. Windows: `Get-PSDrive C`.
3. **Scan (read-only).** Run the bundled scanner if `python3` is available; it
   prints reclaimable space by category and tier and accepts `--json` and
   `--projects <roots...>`. The scanner ships next to this skill at `scripts/scan.py`
   — installed as a plugin it resolves to
   `${CLAUDE_PLUGIN_ROOT}/skills/disk-cleanup/scripts/scan.py`; installed as a bare
   skill, `~/.claude/skills/disk-cleanup/scripts/scan.py`. If Python is absent, size
   the cache/temp/trash dirs with native tools (`du -sh`,
   `Get-ChildItem | Measure-Object -Sum Length`).
4. **Plan.** From the scan, build the concrete list the active profile will remove,
   with sizes. State which tiers are in scope.
5. **Clean.** Run the per-OS commands for the active tiers, skipping absent tools.
   Operate on cache directory *contents*, not the cache directories themselves
   (some apps misbehave if their cache root vanishes). Closing the relevant apps
   first is ideal; in an autonomous run, proceed and note it.
6. **Verify and report.** Record free space after. Write `disk-cleanup-report.md`
   (template at the end). Show the user the report.

## macOS commands

Tier 0 (auto, regenerates):
```bash
# User caches: clear contents, keep the directory
find ~/Library/Caches -mindepth 1 -maxdepth 1 -exec rm -rf {} + 2>/dev/null
# Xcode build products
rm -rf ~/Library/Developer/Xcode/DerivedData/* 2>/dev/null
# Toolchain caches via their own cleaners
command -v brew  >/dev/null && brew cleanup -s && brew autoremove
command -v npm   >/dev/null && npm cache clean --force
command -v pnpm  >/dev/null && pnpm store prune
command -v yarn  >/dev/null && yarn cache clean
command -v pip3  >/dev/null && pip3 cache purge
command -v go    >/dev/null && go clean -cache
# Cargo: prefer cargo-cache; fall back to removing the re-fetchable registry cache
if command -v cargo-cache >/dev/null; then cargo cache --autoclean
else rm -rf ~/.cargo/registry/cache/* ~/.cargo/registry/src/* 2>/dev/null; fi
```

Tier 1 (auto, irreversible):
```bash
rm -rf ~/.Trash/* 2>/dev/null                                   # empty Trash
find ~/Library/Logs -type f -mtime +7 -delete 2>/dev/null       # logs older than 7d
rm -rf ~/Library/Developer/Xcode/iOS\ DeviceSupport/* 2>/dev/null
command -v xcrun >/dev/null && xcrun simctl delete unavailable   # dead simulators
```

Tier 2 (opt-in only):
```bash
# Purgeable space is often the biggest macOS win: thin APFS local Time Machine
# snapshots. Frees up to ~20 GB here. Requires sudo.
sudo tmutil thinlocalsnapshots / 21474836480 4
# Go module cache (re-downloadable)
go clean -modcache
```

## Linux commands

Tier 0 (auto, regenerates):
```bash
find ~/.cache -mindepth 1 -maxdepth 1 -exec rm -rf {} + 2>/dev/null
command -v npm  >/dev/null && npm cache clean --force
command -v pnpm >/dev/null && pnpm store prune
command -v pip3 >/dev/null && pip3 cache purge
command -v go   >/dev/null && go clean -cache
if command -v cargo-cache >/dev/null; then cargo cache --autoclean
else rm -rf ~/.cargo/registry/cache/* ~/.cargo/registry/src/* 2>/dev/null; fi
```

Tier 1 (auto, irreversible):
```bash
rm -rf ~/.local/share/Trash/* 2>/dev/null
```

Tier 2 (opt-in only; detect the distro via /etc/os-release):
```bash
# Debian / Ubuntu
sudo apt-get clean && sudo apt-get autoremove --purge -y
# Fedora / RHEL
sudo dnf clean all && sudo dnf autoremove -y
# Arch (keep last 2 versions)
sudo pacman -Sc --noconfirm; command -v paccache >/dev/null && sudo paccache -rk2
# systemd journal: cap at 200M (or use --vacuum-time=7d)
sudo journalctl --vacuum-size=200M
# snap: drop disabled revisions; flatpak: remove unused runtimes
snap list --all 2>/dev/null | awk '/disabled/{print $1, $3}' | \
  while read -r n r; do sudo snap remove "$n" --revision="$r"; done
command -v flatpak >/dev/null && flatpak uninstall --unused -y
```

## Windows commands (PowerShell)

Tier 0 (auto, regenerates):
```powershell
Remove-Item "$env:TEMP\*" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "$env:LOCALAPPDATA\npm-cache\*" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "$env:LOCALAPPDATA\pip\Cache\*" -Recurse -Force -ErrorAction SilentlyContinue
if (Get-Command cargo-cache -ErrorAction SilentlyContinue) { cargo cache --autoclean }
else { Remove-Item "$env:USERPROFILE\.cargo\registry\cache\*","$env:USERPROFILE\.cargo\registry\src\*" -Recurse -Force -ErrorAction SilentlyContinue }
if (Get-Command npm -ErrorAction SilentlyContinue) { npm cache clean --force }
```

Tier 1 (auto, irreversible):
```powershell
Clear-RecycleBin -Force -ErrorAction SilentlyContinue
```

Tier 2 (opt-in only; most need an elevated shell):
```powershell
# WinSxS / Windows Update component cleanup
Dism.exe /online /Cleanup-Image /StartComponentCleanup
Remove-Item "$env:SystemRoot\Temp\*" -Recurse -Force -ErrorAction SilentlyContinue
# Delivery Optimization cache
Delete-DeliveryOptimizationCache -Force -ErrorAction SilentlyContinue
```

## Developer caches (all platforms)

Docker reclaims a lot but has the sharpest footgun (volumes hold data). Check the
daemon is reachable first with `docker system df` (read-only); if Docker is not
running, skip it and note it — do not start it in an autonomous run.
```bash
docker builder prune -f          # build cache            (Tier 1)
docker image prune -f            # dangling images        (Tier 1)
docker system prune -a -f        # ALL unused images      (Tier 2, opt-in)
# Never pass --volumes in an autonomous run. Volumes hold databases.
```

Rust `target/` directories are the usual disk hog for a Rust developer, but they
belong to live projects. Do not `rm -rf` them blindly.
```bash
# Tier 2, opt-in: remove only artifacts not accessed in 30+ days, recursively.
# Requires cargo-sweep (cargo install cargo-sweep).
cargo sweep -r --time 30 ~/code
# Per-project full clean only when the user names the project:
#   (cd <project> && cargo clean)
```

`node_modules` is Tier 3: report sizes (the scanner's `--projects` flag finds them),
never auto-delete. Removing the `node_modules` of an active project breaks it.

Browser data is Tier 3: clearing a browser cache subdir can also wipe logins and
sessions depending on layout. Report it and leave it to the user.

## Report structure

Write `disk-cleanup-report.md` using this template:

```markdown
# Disk Cleanup Report - <date> - <hostname> (<OS>)

## Free space
- Before: <X> free of <T>
- After:  <Y> free of <T>
- Reclaimed: <Y - X>

## Removed (Tier 0 + Tier 1)
| Category | Tier | Freed |
|---|---|---|
| ... | 0 | ... |
**Total removed: <bytes>**

## Skipped
- <path>: <reason> (protected / ambiguous / tool missing)

## Reclaimable on request (Tier 2 - needs sudo/admin or rebuild)
| Action | Est. reclaim | Command |
|---|---|---|

## Review manually (Tier 3 - never auto-deleted)
| Item | Size | Note |
|---|---|---|
```

## Notes

- Idempotent and re-runnable. Running twice is harmless; the second pass frees ~0.
- Sizes in the scan are an upper bound on reclaim. Active files in a cache may be
  re-created immediately, so actual freed space can be slightly lower.
- **Measure per category.** Size each target with `du -sk` (or equivalent)
  immediately before and after its own deletion to report accurate per-category
  freed bytes. Prefer this over a raw `df` before/after delta: on a busy machine
  (an active multi-crate build, Spotlight reindex, backup, or cloud sync) `df` can
  move by gigabytes for reasons unrelated to the cleanup, and can even fall while
  you free space.
- If `python3` is unavailable, the workflow still holds; only the scan switches to
  native sizing commands.
