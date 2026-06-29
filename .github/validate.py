#!/usr/bin/env python3
"""
CI validation for the clean-my-disk marketplace / plugin / skill.

Mirrors the structural part of `claude plugin validate --strict` (without needing
the CLI) and adds two extra guards specific to a delete-capable skill:
  * the bundled scanner must compile and run read-only, and
  * the SKILL.md bash blocks must contain no dangerous patterns (`sudo rm`, a
    zsh-unsafe `rm -rf <dir>/*` glob, or a bare `rm -rf ~` / `/`).

Run locally from anywhere:  python3 .github/validate.py
Exit code 0 = all good, 1 = one or more failures (printed).
"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

errors = []
def err(msg):
    errors.append(msg)

# 1. plugin.json -----------------------------------------------------------
with open("disk-cleanup/.claude-plugin/plugin.json", encoding="utf-8") as f:
    plugin = json.load(f)
if not re.fullmatch(r"[a-z0-9-]+", plugin.get("name", "")):
    err("plugin.json: name must be kebab-case [a-z0-9-]")
if not re.fullmatch(r"\d+\.\d+\.\d+", plugin.get("version", "")):
    err("plugin.json: version must be semver MAJOR.MINOR.PATCH (no 'v' prefix)")
if not plugin.get("description"):
    err("plugin.json: description is required")

# 2. marketplace.json ------------------------------------------------------
with open(".claude-plugin/marketplace.json", encoding="utf-8") as f:
    market = json.load(f)
if not market.get("name"):
    err("marketplace.json: name is required")
if not (isinstance(market.get("owner"), dict) and market["owner"].get("name")):
    err("marketplace.json: owner must be an object containing a name")
plugins = market.get("plugins")
if not (isinstance(plugins, list) and plugins):
    err("marketplace.json: plugins[] must be a non-empty array")
for entry in plugins or []:
    if not entry.get("name"):
        err("marketplace.json: a plugins[] entry is missing 'name'")
    src = entry.get("source")
    rel = src[2:] if isinstance(src, str) and src.startswith("./") else src
    if not (isinstance(rel, str) and os.path.isdir(rel or ".")):
        err(f"marketplace.json: source '{src}' must be an existing directory")
if plugins and not any(e.get("name") == plugin.get("name") for e in plugins):
    err("marketplace.json: no plugins[] entry matches the plugin.json name")

# 3. SKILL.md frontmatter --------------------------------------------------
SKILL = "disk-cleanup/skills/disk-cleanup/SKILL.md"
text = open(SKILL, encoding="utf-8").read()
fm = re.match(r"^---\n(.*?)\n---\n", text, re.S)
if not fm:
    err("SKILL.md: missing YAML frontmatter")
else:
    body = fm.group(1)
    if "name:" not in body:
        err("SKILL.md: frontmatter needs a name")
    if "description:" not in body:
        err("SKILL.md: frontmatter needs a description")
    if len(body) > 1024:
        err(f"SKILL.md: frontmatter too long ({len(body)} > 1024 chars)")

# 4. Safety invariants inside ```bash code fences --------------------------
bash_blocks = re.findall(r"```bash\n(.*?)```", text, re.S)
for block in bash_blocks:
    for line in block.splitlines():
        code = line.split("#", 1)[0]  # ignore trailing comments
        if re.search(r"\bsudo\s+rm\b", code):
            err(f"SKILL.md bash: 'sudo rm' is forbidden -> {line.strip()}")
        if re.search(r"\brm\s+-rf\s+\S*/\*", code):
            err(f"SKILL.md bash: zsh-unsafe 'rm -rf <dir>/*' (use find) -> {line.strip()}")
        if re.search(r"\brm\s+-rf\s+(/|~|\$HOME)\s*$", code):
            err(f"SKILL.md bash: bare 'rm -rf ~|/|$HOME' -> {line.strip()}")

# 5. Scanner compiles and runs read-only -----------------------------------
SCAN = "disk-cleanup/skills/disk-cleanup/scripts/scan.py"
if subprocess.run([sys.executable, "-m", "py_compile", SCAN]).returncode:
    err("scan.py: does not compile")
else:
    run = subprocess.run([sys.executable, SCAN, "--json"],
                         capture_output=True, text=True)
    if run.returncode:
        err(f"scan.py --json: exited {run.returncode}\n{run.stderr.strip()}")
    else:
        try:
            data = json.loads(run.stdout)
            if not ({"os", "disk", "entries", "tier_totals"} <= set(data)):
                err("scan.py --json: output missing expected keys")
        except Exception as exc:  # noqa: BLE001
            err(f"scan.py --json: output is not valid JSON ({exc})")

# ------------------------------------------------------------------------
if errors:
    print("VALIDATION FAILED:")
    for e in errors:
        print("  -", e)
    sys.exit(1)
print(f"OK: plugin '{plugin['name']}' v{plugin['version']} | "
      f"marketplace '{market['name']}' | frontmatter + {len(bash_blocks)} bash "
      f"blocks + scanner all pass")
