"""Issue 35: the page is the JA design system and nothing else. Run from the repo root:
python3 -m unittest discover -s tests

The tests pass whether $JA_SKILL points at a real skill or at a missing folder (the bundled copy is then
used), and they never use the network.
"""
import html
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
import check_theme_sync  # noqa: E402
from test_offline_build import build, source_dir  # noqa: E402


class BuiltPage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        proc, out = build(cls.tmp.name)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        cls.page = out.read_text(encoding="utf-8")
        cls.src = source_dir()
        cls.tokens = (cls.src / "tokens.css").read_text(encoding="utf-8")
        cls.components = (cls.src / "components.css").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_inlines_tokens_then_components_verbatim(self):
        self.assertIn(self.tokens, self.page)
        self.assertIn(self.components, self.page)
        self.assertLess(self.page.index(self.tokens), self.page.index(self.components))

    def test_no_css_of_its_own_beyond_the_recipe_and_two_justified_rules(self):
        blocks = re.findall(r"<style>(.*?)</style>", self.page, re.S)
        self.assertEqual(len(blocks), 1)
        own = blocks[0].replace(self.tokens, "").replace(self.components, "")
        own = re.sub(r"/\*.*?\*/", "", own, flags=re.S)
        selectors = sorted(s.strip() for s in re.findall(r"([^{}]+)\{", own))
        self.assertEqual(selectors, sorted([
            "body", "h1, h2, h3, h4, p", ".t-display, .ds-prose h1", ".gallery-muted", ".gallery-muted strong",
        ]))
        self.assertNotRegex(own, r"#[0-9a-fA-F]{3,8}\b", "no literal colour")
        self.assertNotRegex(own, r"\d\s*(px|em|rem)\b", "no literal size")
        self.assertNotRegex(own, r"font-family:[ \t]*(?!var\(|[ \t])\S", "no literal font")
        self.assertNotIn("rgba(", own)
        for gone in ("btn-arrow", "lb-bg", "-on-dark", "themebar", "data-open", "@font-face"):
            self.assertNotIn(gone, self.page.replace(self.tokens, "").replace(self.components, ""))

    def test_uses_the_media_and_lightbox_components(self):
        self.assertIn('<div class="ds-media-grid" id="grid">', self.page)
        self.assertIn("'ds-media-card'", self.page)
        self.assertIn("'ds-media-thumb'", self.page)
        self.assertIn('class="ds-lightbox" id="lb"', self.page)
        self.assertIn("ds-lightbox-figure", self.page)
        self.assertIn("classList.add('is-open')", self.page)
        self.assertIn('class="ds-theme-switch"', self.page)
        self.assertIn('<main class="ds-page ds-stack is-loose">', self.page)

    def test_links_the_two_fonts_from_theme_json(self):
        theme = json.loads((self.src / "theme.json").read_text(encoding="utf-8"))
        for role in ("sans", "mono"):
            url = theme["fonts"][role]["css_url"]
            self.assertIn(f'<link rel="stylesheet" href="{html.escape(url, quote=True)}">', self.page)
        self.assertEqual(self.page.count('<link rel="stylesheet"'), 2)

    def test_brand_has_a_light_and_a_dark_logo(self):
        self.assertIn('class="ds-brand-light"', self.page)
        self.assertIn('class="ds-brand-dark"', self.page)


class Fallback(unittest.TestCase):
    def test_missing_skill_folder_uses_the_bundled_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, out = build(tmp, env={"JA_SKILL": str(Path(tmp) / "no-such-skill")})
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("theme: bundled copy in themes/ja", proc.stdout)
            page = out.read_text(encoding="utf-8")
            bundled = check_theme_sync.BUNDLED
            self.assertIn((bundled / "tokens.css").read_text(encoding="utf-8"), page)
            self.assertIn((bundled / "components.css").read_text(encoding="utf-8"), page)

    def test_folder_missing_one_css_file_uses_the_bundled_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            live = Path(tmp) / "skill"
            live.mkdir()
            (live / "tokens.css").write_text(":root{--x:1}")
            proc, out = build(tmp, env={"JA_SKILL": str(live)})
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("theme: bundled copy in themes/ja", proc.stdout)
            self.assertNotIn("--x:1", out.read_text(encoding="utf-8"))

    def test_a_usable_skill_folder_is_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            live = Path(tmp) / "skill"
            live.mkdir()
            (live / "tokens.css").write_text(":root{--marker-tokens:1}")
            (live / "components.css").write_text(".marker-components{color:var(--ink)}")
            proc, out = build(tmp, env={"JA_SKILL": str(live)})
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("theme: JA skill at", proc.stdout)
            page = out.read_text(encoding="utf-8")
            self.assertIn(":root{--marker-tokens:1}", page)
            self.assertIn(".marker-components{color:var(--ink)}", page)
            # no theme.json in that folder: fonts and the brand come from the bundled copy
            self.assertEqual(page.count('<link rel="stylesheet"'), 2)
            self.assertIn('class="ds-brand-light"', page)


class BundledCopy(unittest.TestCase):
    def test_bundled_copy_has_what_the_build_needs(self):
        b = check_theme_sync.BUNDLED
        for rel in ("tokens.css", "components.css", "GENERATED", "theme.json", "assets/mark.svg", "assets/mark-dark.svg"):
            self.assertTrue((b / rel).is_file(), rel)

    def test_old_own_values_are_gone(self):
        self.assertEqual(sorted(p.name for p in (SKILL / "themes").iterdir()), ["ja"])
        self.assertFalse((SKILL / "fonts").exists())


if __name__ == "__main__":
    unittest.main()
