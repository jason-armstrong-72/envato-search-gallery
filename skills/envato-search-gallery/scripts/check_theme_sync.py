#!/usr/bin/env python3
"""Check that the bundled theme is in step with the master theme, and refresh it.

Usage:
    check_theme_sync.py                 compare and report
    check_theme_sync.py --update        rewrite the bundled theme from the master
    check_theme_sync.py --theme-file P  work on another copy of the bundled theme (for testing)

The master is the theme.json in the jason-armstrong-design-system skill. Find it at
$JA_THEME_MASTER if that is set, else ~/.claude/skills/<sync.source>/theme.json.

The bundled copy keeps a few plugin-local values (the dotted paths in sync.local_keys: the
embedded fonts, the logo paths and the sync block). Everything else must equal the master.

Only the theme copy is compared. The gallery's own jason-armstrong.layout.json is never read here.

Exit code: 0 when in step or when no master exists (the plugin may be installed alone),
1 when a master exists and differs. Standard library only.
"""
import argparse
import copy
import json
import os
import shutil
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
BUNDLED = SKILL_DIR / "themes" / "jason-armstrong.json"
SHORT = 80


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def master_path(bundled):
    env = os.environ.get("JA_THEME_MASTER")
    if env:
        return Path(env).expanduser()
    source = (bundled.get("sync") or {}).get("source", "jason-armstrong-design-system")
    return Path.home() / ".claude" / "skills" / source / "theme.json"


def flatten(value, prefix=""):
    """Leaf values by dotted path. Lists count as one leaf."""
    if isinstance(value, dict) and value:
        out = {}
        for k, v in value.items():
            out.update(flatten(v, f"{prefix}.{k}" if prefix else k))
        return out
    return {prefix: value}


def ignored(path, local_keys):
    return any(path == k or path.startswith(k + ".") for k in local_keys)


def differences(bundled, master, local_keys):
    """List of (path, bundled value, master value) outside the local keys."""
    a, b = flatten(bundled), flatten(master)
    missing = object()
    out = []
    for path in sorted(set(a) | set(b)):
        if ignored(path, local_keys):
            continue
        va, vb = a.get(path, missing), b.get(path, missing)
        if va != vb:
            out.append((path, "(absent)" if va is missing else va, "(absent)" if vb is missing else vb))
    return out


def short(value):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text if len(text) <= SHORT else text[: SHORT - 3] + "..."


def set_path(tree, dotted, value):
    keys = dotted.split(".")
    for k in keys[:-1]:
        tree = tree.setdefault(k, {})
    tree[keys[-1]] = value


def get_path(tree, dotted):
    for k in dotted.split("."):
        if not isinstance(tree, dict) or k not in tree:
            return False, None
        tree = tree[k]
    return True, tree


def rebuilt(bundled, master):
    """The master's content with the bundled theme's local values put back."""
    new = copy.deepcopy(master)
    sync = bundled.get("sync") or {}
    for key in sync.get("local_keys", []):
        found, value = get_path(bundled, key)
        if found:
            set_path(new, key, copy.deepcopy(value))
    new["sync"] = copy.deepcopy(sync)
    new["sync"]["source_version"] = master.get("version")
    return new


def behind_note(bundled_path=BUNDLED):
    """A one-line reason the bundled theme is behind the master, or None. Never raises."""
    try:
        bundled = load(bundled_path)
        mp = master_path(bundled)
        if not mp.is_file():
            return None
        master = load(mp)
        if differences(bundled, master, (bundled.get("sync") or {}).get("local_keys", [])):
            return "theme copy is behind the master: run scripts/check_theme_sync.py"
    except Exception:
        return None
    return None


def copy_logos(bundled, new, master, mp):
    """Copy the master's logo files into the bundled theme's asset paths. Returns notes."""
    notes = []
    for field in ("logo", "logo_dark"):
        src_name = (master.get("brand") or {}).get(field)
        if not src_name:
            continue
        src = Path(src_name)
        src = src if src.is_absolute() else mp.parent / src
        local = (new.get("brand") or {}).get(field) or f"themes/assets/{Path(src_name).name}"
        dest = SKILL_DIR / local
        if not src.is_file():
            notes.append(f"logo not found in the master, left alone: {src}")
            continue
        if dest.is_file() and dest.read_bytes() == src.read_bytes():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        notes.append(f"copied {src.name} to {dest.relative_to(SKILL_DIR)}")
    return notes


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--update", action="store_true", help="rewrite the bundled theme from the master")
    ap.add_argument("--theme-file", default=str(BUNDLED), help="the bundled theme to check or rewrite")
    args = ap.parse_args()

    tf = Path(args.theme_file)
    bundled = load(tf)
    mp = master_path(bundled)
    if not mp.is_file():
        print(f"master not found at {mp}: nothing to compare")
        return 0
    master = load(mp)
    local_keys = (bundled.get("sync") or {}).get("local_keys", [])
    diffs = differences(bundled, master, local_keys)
    name, mver, bver = master.get("name", "?"), master.get("version", "?"), bundled.get("version", "?")

    if not args.update:
        if not diffs:
            print(f"in step: {name} {mver}")
            return 0
        print(f"behind: bundled {bver}, master {mver}")
        for path, old, new in diffs:
            print(f"{path}\n  bundled: {short(old)}\n  master:  {short(new)}")
        return 1

    new = rebuilt(bundled, master)
    notes = copy_logos(bundled, new, master, mp)
    text = json.dumps(new, indent=2, ensure_ascii=False) + "\n"
    changed = text != tf.read_text(encoding="utf-8")
    if changed:
        tf.write_text(text, encoding="utf-8")
    if not diffs and not notes and not changed:
        print(f"already in step: {name} {mver}")
        return 0
    print(f"updated {tf}: {bver} -> {mver}, {len(diffs)} value(s) changed")
    for path, old, newv in diffs:
        print(f"  {path}: {short(old)} -> {short(newv)}")
    for n in notes:
        print(f"  {n}")
    print("local values kept: " + ", ".join(local_keys))
    return 0


if __name__ == "__main__":
    sys.exit(main())
