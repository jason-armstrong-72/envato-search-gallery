"""Issue 30: only the colour variables the page reads are written. Run from the repo root:
python3 -m unittest discover -s tests
"""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "envato-search-gallery"
sys.path.insert(0, str(SKILL / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
import build_gallery  # noqa: E402
from test_offline_build import build  # noqa: E402

COLOURS = {n: {"light": f"#0{i}0000", "dark": f"#0{i}1111"} for i, n in enumerate(build_gallery.REQUIRED_COLOURS)}


class UsedColours(unittest.TestCase):
    def test_scan(self):
        read = build_gallery.used_colours("a{color:var(--ink);border:1px solid var(--border,red)}b{--x:var(--btn-bg)}")
        self.assertEqual(read, {"ink", "border", "btn-bg"})


class ThemeVarsColours(unittest.TestCase):
    def theme(self, colour=None):
        t = json.loads((SKILL / "themes" / "jason-armstrong.json").read_text(encoding="utf-8"))
        t["colour"] = colour or COLOURS
        return t

    def test_only_read_colours_are_written(self):
        out = build_gallery.theme_vars(self.theme(), None, {"ink", "bg"})
        self.assertIn("--ink:#030000;", out)
        self.assertIn("--bg:#000000;", out)
        self.assertNotIn("--error:", out)
        self.assertNotIn("--warning:", out)
        self.assertIn("color-scheme:dark;", out)

    def test_on_dark_only_when_read(self):
        theme = self.theme()
        self.assertNotIn("--accent-on-dark", build_gallery.theme_vars(theme, None, {"ink"}))
        self.assertIn("--accent-on-dark:", build_gallery.theme_vars(theme, None, {"accent-on-dark"}))

    def test_var_chain_keeps_the_target(self):
        colour = dict(COLOURS, ink={"light": "var(--bg)", "dark": "var(--bg)"})
        out = build_gallery.theme_vars(self.theme(colour), None, {"ink"})
        self.assertIn("--bg:", out)

    def test_no_scan_writes_everything(self):
        out = build_gallery.theme_vars(self.theme())
        for name in COLOURS:
            self.assertIn(f"--{name}:", out)


class BuiltPage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        proc, out = build(cls.tmp.name)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        page = out.read_text(encoding="utf-8")
        css = re.search(r"<style>(.*?)</style>", page, re.S).group(1)
        cls.css = re.sub(r"@font-face\{[^}]*\}", "", css)
        cls.page = page

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_colour_written_is_read_and_every_read_is_written(self):
        names = set(build_gallery.REQUIRED_COLOURS) | {"accent-on-dark", "ink-on-dark", "muted-on-dark"}
        defined = {n for n in re.findall(r"--([\w-]+):", self.css) if n in names}
        read = {n for n in re.findall(r"var\(--([\w-]+)", self.css) if n in names}
        self.assertEqual(defined - read, set(), "colour variables written but never read")
        self.assertEqual(read - defined, set(), "colour variables read but never written")

    def test_unused_colours_are_left_out(self):
        self.assertNotIn("--error:", self.page)
        self.assertNotIn("--warning:", self.page)

    def test_used_colours_are_in_both_modes(self):
        self.assertIn('--bg:#f1f1f0;', self.page)
        self.assertIn('--bg:#000000;', self.page)


if __name__ == "__main__":
    unittest.main()
