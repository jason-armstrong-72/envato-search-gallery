"""Build a gallery from references/offline-input.json (local placeholder images, no network) and check
the page. Run from the repo root:  python3 -m unittest discover -s tests
"""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "envato-search-gallery"
SCRIPTS = SKILL / "scripts"
INPUT = SKILL / "references" / "offline-input.json"
THEME = json.loads((SKILL / "themes" / "jason-armstrong.json").read_text(encoding="utf-8"))

sys.path.insert(0, str(SCRIPTS))
import build_gallery  # noqa: E402


def build(out_dir, input_path=INPUT):
    out = Path(out_dir) / "gallery.html"
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "build_gallery.py"), str(input_path), "--out", str(out), "--no-serve"],
        capture_output=True, text=True, timeout=60,
    )
    return proc, out


class OfflineBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.proc, cls.out = build(cls.tmp.name)
        cls.spec = json.loads(INPUT.read_text(encoding="utf-8"))
        cls.page = cls.out.read_text(encoding="utf-8") if cls.out.exists() else ""

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_builds(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stdout + self.proc.stderr)
        self.assertIn("open:", self.proc.stdout)

    def test_title_and_query(self):
        query = self.spec["query"]
        self.assertIn(f"<title>Envato results: {query}</title>", self.page)
        self.assertIn(f"&ldquo;{query}&rdquo;", self.page)

    def test_one_card_per_item(self):
        data = re.search(r'<script type="application/json" id="data">(.*?)</script>', self.page, re.S)
        items = json.loads(data.group(1))
        self.assertEqual(len(items), len(self.spec["results"]))
        self.assertEqual([i["title"] for i in items], [r["title"] for r in self.spec["results"]])
        for item in items:
            self.assertTrue(item["src"].startswith("data:image/svg+xml;base64,"))
        self.assertIn(f"<strong>{len(items)}</strong> results", self.page)

    def test_theme_colours(self):
        for name, modes in THEME["colour"].items():
            if name not in build_gallery.REQUIRED_COLOURS:
                continue
            for mode in ("light", "dark"):
                self.assertIn(f"--{name}:{modes[mode]};", self.page, f"{name} ({mode})")

    def test_theme_fonts(self):
        for role in ("sans", "mono"):
            self.assertIn(THEME["fonts"][role]["family"], self.page)
        self.assertIn("@font-face", self.page)
        self.assertIn("data:font/woff2;base64,", self.page)

    def test_only_used_properties_are_written(self):
        css = re.search(r"<style>(.*?)</style>", self.page, re.S).group(1)
        css = re.sub(r"@font-face\{[^}]*\}", "", css)
        defined = set(re.findall(r"(--(?:t|sp)-[\w-]+):", css))
        used = set(re.findall(r"var\((--(?:t|sp)-[\w-]+)\)", css))
        self.assertEqual(defined - used, set(), "custom properties written but never read")
        self.assertEqual(used - defined, set(), "custom properties read but never written")

    def test_unused_roles_are_left_out(self):
        self.assertNotIn("--t-h2-s", self.page)
        self.assertNotIn("--sp-gap:", self.page)
        self.assertIn("--t-display-s", self.page)
        self.assertIn("--sp-cardmin", self.page)


class ExampleInput(unittest.TestCase):
    def test_example_placeholder_url_is_legal(self):
        # the example cannot build (placeholder signature) but its URL must be legal, so the builder says
        # "Wrong signature" instead of crashing
        example = SKILL / "references" / "example-input.json"
        data = json.loads(example.read_text(encoding="utf-8"))
        for item in data["results"]:
            self.assertNotRegex(item["img"], r"[\s<>]", "placeholder URL must be a legal URL")


class UsedVars(unittest.TestCase):
    def test_scan(self):
        type_props, spacing = build_gallery.used_vars("a{font-size:var(--t-meta-s);gap:var(--sp-gridgap)}")
        self.assertEqual(type_props, {"meta": {"s"}})
        self.assertEqual(spacing, {"gridgap"})


if __name__ == "__main__":
    unittest.main()
