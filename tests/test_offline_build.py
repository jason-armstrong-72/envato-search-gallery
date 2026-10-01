"""Build a gallery from references/offline-input.json (local placeholder images, no network) and check
the page. Run from the repo root:  python3 -m unittest discover -s tests
"""
import json
import os
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

sys.path.insert(0, str(SCRIPTS))
import check_theme_sync  # noqa: E402


def source_dir():
    """Where a build reads the design system from: the live skill if usable, else the bundled copy."""
    live = check_theme_sync.live_dir()
    return live if check_theme_sync.live_usable(live) else check_theme_sync.BUNDLED


def build(out_dir, input_path=INPUT, env=None):
    """Run the builder. `env` adds to or replaces variables of this process's environment."""
    out = Path(out_dir) / "gallery.html"
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "build_gallery.py"), str(input_path), "--out", str(out), "--no-serve"],
        capture_output=True, text=True, timeout=60, env={**os.environ, **(env or {})},
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

    def test_prints_which_source_was_used(self):
        self.assertRegex(self.proc.stdout, r"(?m)^theme: (JA skill at|bundled copy in themes/ja)")


class ExampleInput(unittest.TestCase):
    def test_example_placeholder_url_is_legal(self):
        # the example cannot build (placeholder signature) but its URL must be legal, so the builder says
        # "Wrong signature" instead of crashing
        example = SKILL / "references" / "example-input.json"
        data = json.loads(example.read_text(encoding="utf-8"))
        for item in data["results"]:
            self.assertNotRegex(item["img"], r"[\s<>]", "placeholder URL must be a legal URL")


if __name__ == "__main__":
    unittest.main()
