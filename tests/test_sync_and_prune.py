"""Tests for the JA copy sync check and the server's start-up pruning.

Run from the repo root: python3 -m unittest discover -s tests
Uses temporary folders only. It never touches ~/.cache/envato-gallery or the real JA skill.
"""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "envato-search-gallery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import check_theme_sync  # noqa: E402
import gallery_server  # noqa: E402

DAY = 86400


def theme_json(logo="assets/m.svg", logo_dark="assets/md.svg"):
    return json.dumps({"name": "T", "brand": {"logo": logo, "logo_dark": logo_dark}})


FILES = {
    "tokens.css": ":root{--a:1}", "components.css": ".ds-x{color:var(--a)}",
    "GENERATED": "generator: t\ntheme: t 1.0.0\n", "assets/m.svg": "<svg>m</svg>", "assets/md.svg": "<svg>md</svg>",
}


def write_skill(folder, files=FILES, **brand):
    folder = Path(folder)
    for rel, text in files.items():
        (folder / rel).parent.mkdir(parents=True, exist_ok=True)
        (folder / rel).write_text(text)
    (folder / "theme.json").write_text(theme_json(**brand))


class SyncFiles(unittest.TestCase):
    """check_theme_sync compares themes/ja with the live skill, byte for byte."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.live = root / "live"
        self.bundled = root / "bundled"
        write_skill(self.live)
        write_skill(self.bundled)
        self.old_env = os.environ.get("JA_SKILL")
        os.environ["JA_SKILL"] = str(self.live)

    def tearDown(self):
        if self.old_env is None:
            os.environ.pop("JA_SKILL", None)
        else:
            os.environ["JA_SKILL"] = self.old_env
        self.tmp.cleanup()

    def run_main(self, *extra):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = check_theme_sync.main(["--bundled", str(self.bundled), *extra])
        return code, out.getvalue()

    def test_identical_is_in_step(self):
        code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assertIn("in step", out)

    def test_each_differing_file_is_named_and_exits_1(self):
        for rel in ("tokens.css", "components.css", "GENERATED", "theme.json", "assets/md.svg"):
            with self.subTest(rel=rel):
                write_skill(self.bundled)
                (self.bundled / rel).write_text("changed")
                code, out = self.run_main()
                self.assertEqual(code, 1)
                self.assertIn("behind", out)
                self.assertIn(f"  {rel}\n", out)
                self.assertEqual(out.count("\n  "), 1, "only that file is listed")

    def test_missing_bundled_file_is_behind(self):
        (self.bundled / "assets" / "m.svg").unlink()
        code, out = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("assets/m.svg", out)

    def test_update_copies_the_files(self):
        (self.live / "tokens.css").write_text(":root{--a:2}")
        (self.live / "assets" / "m.svg").write_text("<svg>new</svg>")
        code, out = self.run_main("--update")
        self.assertEqual(code, 0)
        self.assertEqual((self.bundled / "tokens.css").read_text(), ":root{--a:2}")
        self.assertEqual((self.bundled / "assets" / "m.svg").read_text(), "<svg>new</svg>")
        code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assertIn("in step", out)

    def test_update_into_an_empty_folder_creates_everything(self):
        empty = Path(self.tmp.name) / "fresh"
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = check_theme_sync.main(["--bundled", str(empty), "--update"])
        self.assertEqual(code, 0)
        for rel in list(FILES) + ["theme.json"]:
            self.assertTrue((empty / rel).is_file(), rel)

    def test_null_logo_field_compares_nothing(self):
        write_skill(self.live, logo=None, logo_dark=None)
        write_skill(self.bundled, logo=None, logo_dark=None)
        (self.bundled / "assets" / "m.svg").write_text("anything")
        code, _ = self.run_main()
        self.assertEqual(code, 0)

    def test_no_live_skill_exits_0_and_says_so(self):
        os.environ["JA_SKILL"] = str(Path(self.tmp.name) / "nope")
        code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assertIn("nothing to compare", out)
        code, out = self.run_main("--update")
        self.assertEqual(code, 0)

    def test_behind_note(self):
        self.assertIsNone(check_theme_sync.behind_note(self.live, self.bundled))
        (self.live / "assets" / "md.svg").write_text("new")
        self.assertIsNotNone(check_theme_sync.behind_note(self.live, self.bundled))
        self.assertIsNone(check_theme_sync.behind_note(Path(self.tmp.name) / "nope", self.bundled))


def page(title="cats"):
    return f'<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<title>Envato results: {title}</title>\n'


class Prune(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def make(self, name, text, age_days):
        p = self.dir / name
        p.write_text(text)
        t = time.time() - age_days * DAY
        os.utime(p, (t, t))
        return p

    def test_prune(self):
        old = self.make("old-cats.html", page(), 8)
        new = self.make("new-dogs.html", page("dogs"), 1)
        tuner = self.make("ja-tuner.html", "<!doctype html><title>Tuner</title>", 30)
        chart = self.make("ja-chart-colours.html", "<!doctype html><title>Colours</title>", 30)
        sneaky = self.make("old-lookalike.html", "<title>Something else</title>", 30)
        state = self.make(".server.json", "{}", 30)
        notes = self.make("notes.txt", "x", 30)
        upper = self.make("Old_Page.html", page(), 30)
        removed = gallery_server.prune(self.dir)
        self.assertEqual(removed, 1)
        self.assertFalse(old.exists())
        for p in (new, tuner, chart, sneaky, state, notes, upper):
            self.assertTrue(p.exists(), p.name)

    def test_name_pattern_matches_builder_slugs_only(self):
        import re
        sys.path.insert(0, str(SCRIPTS))
        slug = lambda t: re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:48] or "results"  # noqa: E731
        for q in ("Cats & Dogs", "coffee shop", "", "---", "A" * 100):
            self.assertTrue(gallery_server.PAGE_NAME.fullmatch(slug(q) + ".html"), q)
        for n in ("Ja_Tuner.html", "a.b.html", ".hidden.html", "-x.html", "x.htm"):
            self.assertFalse(gallery_server.PAGE_NAME.fullmatch(n), n)

    def test_missing_folder(self):
        self.assertEqual(gallery_server.prune(self.dir / "nope"), 0)

    def test_server_start_prunes(self):
        old = self.make("old-cats.html", page(), 8)
        tuner = self.make("ja-tuner.html", "<title>Tuner</title>", 30)
        proc = subprocess.Popen(
            [sys.executable, str(SCRIPTS / "gallery_server.py"), "run", "--dir", str(self.dir), "--idle", "5"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            for _ in range(50):
                if (self.dir / ".server.json").exists():
                    break
                time.sleep(0.1)
            self.assertTrue((self.dir / ".server.json").exists())
            self.assertFalse(old.exists())
            self.assertTrue(tuner.exists())
        finally:
            proc.terminate()
            proc.wait(timeout=10)


if __name__ == "__main__":
    unittest.main()
