#!/usr/bin/env python3
"""Check that the bundled copy of the JA design system is in step with the installed skill, and refresh it.

Usage:
    check_theme_sync.py                 compare and report
    check_theme_sync.py --update        copy the live skill's files over the bundled copy
    check_theme_sync.py --bundled DIR   work on another bundled folder (for testing)

The live skill is the jason-armstrong-design-system folder: $JA_SKILL if that is set, else
~/.claude/skills/jason-armstrong-design-system. The bundled copy is themes/ja/ in this plugin.

These files are compared byte for byte: tokens.css, components.css, GENERATED, theme.json and the logo
files that the live theme.json brand points at (brand.logo and brand.logo_dark, relative to the skill
folder, kept at the same path under themes/ja/). A logo field that is null has nothing to compare.

Exit code: 0 when in step or when there is no live skill (the plugin may be installed alone),
1 when a live skill exists and differs. Standard library only.
"""
import argparse
import json
import os
import shutil
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
BUNDLED = SKILL_DIR / "themes" / "ja"
SKILL_NAME = "jason-armstrong-design-system"
BASE_FILES = ("tokens.css", "components.css", "GENERATED", "theme.json")
REQUIRED = ("tokens.css", "components.css")


def live_dir():
    """The folder of the installed JA skill: $JA_SKILL if set, else ~/.claude/skills/<name>."""
    env = os.environ.get("JA_SKILL")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".claude" / "skills" / SKILL_NAME


def live_usable(live):
    """True when the folder holds both CSS files the page is built from."""
    return all((Path(live) / name).is_file() for name in REQUIRED)


def logo_paths(theme_json):
    """The relative paths of the logo files a theme.json names, light first. Never raises."""
    try:
        brand = json.loads(Path(theme_json).read_text(encoding="utf-8")).get("brand") or {}
    except (OSError, ValueError, AttributeError):
        return []
    return [p for p in (brand.get("logo"), brand.get("logo_dark")) if isinstance(p, str) and p]


def file_list(live):
    """Relative paths to compare: the base files, then the live theme.json's logo files."""
    return list(BASE_FILES) + logo_paths(Path(live) / "theme.json")


def differences(live, bundled=BUNDLED):
    """Relative paths whose bytes differ, or that are missing from the bundled copy.

    A file the live skill does not have is skipped (nothing to compare).
    """
    out = []
    for rel in file_list(live):
        src = Path(live) / rel
        if not src.is_file():
            continue
        dest = Path(bundled) / rel
        if not dest.is_file() or dest.read_bytes() != src.read_bytes():
            out.append(rel)
    return out


def behind_note(live=None, bundled=BUNDLED):
    """A one-line reason the bundled copy is behind the live skill, or None. Never raises."""
    try:
        live = live_dir() if live is None else Path(live)
        if not live.is_dir():
            return None
        if differences(live, bundled):
            return "bundled copy in themes/ja is behind the JA skill: run scripts/check_theme_sync.py --update"
    except Exception:
        return None
    return None


def version_of(folder):
    """The theme line of a GENERATED file, for messages. Empty when there is none."""
    try:
        for line in (Path(folder) / "GENERATED").read_text(encoding="utf-8").splitlines():
            if line.startswith("theme:"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return ""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--update", action="store_true", help="copy the live skill's files over the bundled copy")
    ap.add_argument("--bundled", default=str(BUNDLED), help="the bundled folder to check or rewrite")
    args = ap.parse_args(argv)

    bundled = Path(args.bundled)
    live = live_dir()
    if not live_usable(live):
        print(f"JA skill not found at {live}: nothing to compare")
        return 0
    diffs = differences(live, bundled)
    ver = version_of(live) or "?"

    if not args.update:
        if not diffs:
            print(f"in step: {ver}")
            return 0
        print(f"behind: bundled {version_of(bundled) or '?'}, JA skill {ver}")
        for rel in diffs:
            print(f"  {rel}")
        return 1

    if not diffs:
        print(f"already in step: {ver}")
        return 0
    for rel in diffs:
        dest = bundled / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(live / rel, dest)
    print(f"updated {bundled}: {version_of(bundled) or '?'}, {len(diffs)} file(s) copied")
    for rel in diffs:
        print(f"  {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
