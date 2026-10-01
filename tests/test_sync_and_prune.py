"""Tests for the theme sync check (logo files) and the server's start-up pruning.

Run from the repo root: python3 -m unittest discover -s tests
Uses temporary folders only. It never touches ~/.cache/envato-gallery or the real master theme.
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


def theme(logo="themes/assets/mark.svg", logo_dark="themes/assets/mark-dark.svg", **brand):
    return {
        "name": "T", "version": "2.0.0", "colours": {"ink": "#000"},
        "brand": dict({"logo": logo, "logo_dark": logo_dark}, **brand),
        "sync": {"source": "x", "local_keys": ["sync", "brand.logo", "brand.logo_dark"]},
    }


class SyncLogos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.skill = root / "skill"
        (self.skill / "themes" / "assets").mkdir(parents=True)
        self.master_dir = root / "master"
        (self.master_dir / "assets").mkdir(parents=True)
        self.master = self.master_dir / "theme.json"
        self.master.write_text(json.dumps(theme("assets/m.svg", "assets/md.svg")))
        self.bundled = self.skill / "themes" / "jason-armstrong.json"
        self.bundled.write_text(json.dumps(theme()))
        for d, name in ((self.master_dir / "assets", "m.svg"), (self.master_dir / "assets", "md.svg")):
            (d / name).write_text(f"<svg>{name}</svg>")
        (self.skill / "themes" / "assets" / "mark.svg").write_text("<svg>m.svg</svg>")
        (self.skill / "themes" / "assets" / "mark-dark.svg").write_text("<svg>md.svg</svg>")
        self.old_skill = check_theme_sync.SKILL_DIR
        check_theme_sync.SKILL_DIR = self.skill
        self.old_env = os.environ.get("JA_THEME_MASTER")
        os.environ["JA_THEME_MASTER"] = str(self.master)

    def tearDown(self):
        check_theme_sync.SKILL_DIR = self.old_skill
        if self.old_env is None:
            os.environ.pop("JA_THEME_MASTER", None)
        else:
            os.environ["JA_THEME_MASTER"] = self.old_env
        self.tmp.cleanup()

    def run_main(self, *extra):
        out = io.StringIO()
        argv = sys.argv
        sys.argv = ["check_theme_sync.py", "--theme-file", str(self.bundled), *extra]
        try:
            with contextlib.redirect_stdout(out):
                code = check_theme_sync.main()
        finally:
            sys.argv = argv
        return code, out.getvalue()

    def test_identical_logos_in_step(self):
        code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assertIn("in step", out)

    def test_differing_logo_is_behind_and_names_the_file(self):
        (self.master_dir / "assets" / "md.svg").write_text("<svg>changed</svg>")
        code, out = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("behind", out)
        self.assertIn("mark-dark.svg", out)
        self.assertNotIn("mark.svg\n", out.replace("mark-dark.svg", ""))

    def test_missing_bundled_logo_is_behind(self):
        (self.skill / "themes" / "assets" / "mark.svg").unlink()
        code, out = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("mark.svg", out)

    def test_update_copies_the_logo(self):
        (self.master_dir / "assets" / "m.svg").write_text("<svg>new</svg>")
        code, out = self.run_main("--update")
        self.assertEqual(code, 0)
        self.assertIn("mark.svg", out)
        self.assertEqual((self.skill / "themes" / "assets" / "mark.svg").read_text(), "<svg>new</svg>")
        code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assertIn("in step", out)

    def test_behind_note_reports_logo_only_change(self):
        (self.master_dir / "assets" / "m.svg").write_text("<svg>new</svg>")
        self.assertIsNotNone(check_theme_sync.behind_note(self.bundled))

    def test_null_master_logo_compares_nothing(self):
        self.master.write_text(json.dumps(theme(None, None)))
        code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assertIn("in step", out)
        code, _ = self.run_main("--update")
        self.assertEqual(code, 0)

    def test_null_logo_in_one_field_only(self):
        self.master.write_text(json.dumps(theme("assets/m.svg", None)))
        (self.skill / "themes" / "assets" / "mark-dark.svg").write_text("anything")
        code, _ = self.run_main()
        self.assertEqual(code, 0)


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
