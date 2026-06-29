# clean-my-disk

**A safe, free disk-cleanup skill for [Claude Code](https://claude.com/claude-code).**
Reclaim disk space on **macOS, Linux, and Windows** — without paying for CleanMyMac,
DaisyDisk, or BleachBit. Install it once, then just tell Claude *"my disk is full"*.

It is built on one principle paid cleaners get right and most `rm -rf` scripts get
wrong: **measure first, delete only what is known to be disposable, and show you the
bill.** It scans **read-only**, reports what it *could* reclaim grouped by risk tier,
then deletes **only** an allowlist of regenerable caches, temp files, and trash. Your
documents, keys, app data, sync folders, VM images, and source trees are never touched.

---

## Why

Agents with delete permission are powerful and dangerous. "Find big files and delete
them" is exactly how you lose irreplaceable data. This skill encodes the restraint a
good cleaner has:

- **Allowlist, not heuristics.** It removes only enumerated cache/temp/trash
  locations. Big ≠ deletable. Large files are *reported*, never auto-removed.
- **Native cleaners first.** `brew cleanup`, `npm cache clean`, `docker builder
  prune`, `Clear-RecycleBin`, etc. understand their own data and fail safe. Raw `rm`
  is the last resort, and only ever on cache *contents*.
- **A hard protected list.** Credentials, Application Support, iCloud/Dropbox/OneDrive
  sync roots, VM disk images, Docker volumes, and `.git`/source trees are off-limits,
  always — even under an "autonomous" or `bypassPermissions` run.
- **Measure → plan → clean → report.** You always get a `disk-cleanup-report.md` with
  per-category bytes freed and a list of everything skipped and why.

## The tier system

| Tier | Meaning | Auto-deleted? | Examples |
|------|---------|---------------|----------|
| **0** | Regenerates automatically, zero data loss | ✅ yes | app caches, `DerivedData`, npm/pip/cargo/go caches |
| **1** | Safe but irreversible | ✅ yes | Trash/Recycle Bin, logs >7 days, dead simulators, Docker build cache & dangling images |
| **2** | Needs sudo/admin or is expensive to rebuild | ⛔ opt-in only | OS package caches, `journalctl --vacuum`, `docker system prune -a`, `cargo sweep`, Time Machine snapshot thinning |
| **3** | Report-only, never auto-deleted | ⛔ never | `node_modules`, VM images, Downloads, Go/Docker module stores, large user files |

Default profile is **Tier 0 + Tier 1**. Tier 2 runs only when you explicitly ask.
Tier 3 is always just a report with sizes and the exact commands, so *you* decide.

## Install

### Option A — as a plugin (recommended)

In Claude Code:

```text
/plugin marketplace add richer-richard/clean-my-disk
/plugin install disk-cleanup@clean-my-disk
```

Then just ask, e.g. *"clean up my disk"*, *"why is my disk full?"*, or run the skill
directly with `/disk-cleanup`.

### Option B — as a bare skill (no plugin system)

```bash
git clone https://github.com/richer-richard/clean-my-disk
cp -r clean-my-disk/disk-cleanup/skills/disk-cleanup ~/.claude/skills/disk-cleanup
```

(Use `.claude/skills/` inside a project to scope it to that project instead.)

## Usage

Once installed, Claude invokes it when you mention freeing disk space, or you can run
`/disk-cleanup`. A typical run:

1. Detects your OS and records free space.
2. Runs the **read-only** scanner (`scripts/scan.py`) and prints reclaimable space by
   category and tier.
3. Shows the plan (what it will remove, with sizes).
4. Cleans Tier 0 + Tier 1 using native tools, skipping anything not installed.
5. Writes `disk-cleanup-report.md` with bytes freed, skips, and the Tier 2/Tier 3
   menu of what you could reclaim manually.

**Opt into Tier 2** by saying so explicitly, e.g. *"also do the sudo/package-cache
cleanup"* or *"run cargo sweep on my code"*.

### The scanner

`scripts/scan.py` is pure-stdlib Python 3 and **never deletes anything** — it only
walks known cache/temp/trash locations and sizes them. It is symlink/junction-safe so
it cannot wander out of a cache dir into your data.

```bash
python3 scan.py                          # table of reclaimable space by tier
python3 scan.py --json                   # machine-readable
python3 scan.py --projects ~/code ~/src  # also size Rust target/ and node_modules (report-only)
```

## What it will never do

- Never `sudo rm`. Never delete outside a known cache/temp/trash location.
- Never touch `~/Documents`, `~/Desktop`, `~/Downloads`, `~/Pictures`, `~/Movies`,
  `~/Music`, `~/.ssh`, `~/.gnupg`, Keychains, `*.pem`/`*.key`, password vaults,
  `~/Library/Application Support`, `~/.config`, `%APPDATA%`.
- Never delete inside iCloud / Dropbox / Google Drive / OneDrive / Syncthing roots.
- Never delete VM images (`*.qcow2`, `*.vmdk`, `*.vdi`, `*.utm`, …) or Docker volumes.
- Never `rm -rf` a repo working tree or its `.git`; build artifacts only via
  `cargo clean` / `cargo sweep` / `go clean` and only when you name the project.
- Never thin Time Machine snapshots with `rm` (only `tmutil`, and only as Tier 2).

## Supported platforms

| OS | Status |
|----|--------|
| macOS (Apple Silicon & Intel) | ✅ |
| Linux (Debian/Ubuntu, Fedora/RHEL, Arch; snap/flatpak) | ✅ |
| Windows (PowerShell) | ✅ |

## Uninstall

```text
/plugin uninstall disk-cleanup@clean-my-disk
/plugin marketplace remove clean-my-disk
```

Or, for a bare skill: `rm -rf ~/.claude/skills/disk-cleanup`.

## Contributing

Issues and PRs welcome — especially additional safe Tier 0/Tier 1 cache locations and
per-distro coverage. Please keep the safety model intact: new deletions must be
regenerable, allowlisted, and prefer a native cleaner. When in doubt, make it Tier 3
(report-only). See [`disk-cleanup/skills/disk-cleanup/SKILL.md`](disk-cleanup/skills/disk-cleanup/SKILL.md)
for the full rules.

## License

[MIT](LICENSE) © Richard Huang. Use at your own risk; this tool deletes files. It is
deliberately conservative, but you are responsible for reviewing the report.
