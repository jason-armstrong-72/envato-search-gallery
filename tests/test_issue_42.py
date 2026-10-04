"""Issue 42: the gallery links the schema 4 fonts (heading, body, mono), and still reads a schema 3 sans."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "envato-search-gallery" / "scripts"))
import build_gallery  # noqa: E402


def font(url):
    return {"family": "X", "css_url": url}


class FontLinks(unittest.TestCase):
    def test_schema_4_body_and_mono(self):
        out = build_gallery.font_links({"fonts": {"body": font("https://f/body"), "mono": font("https://f/mono")}})
        self.assertEqual(out, '<link rel="stylesheet" href="https://f/body">\n<link rel="stylesheet" href="https://f/mono">')

    def test_schema_4_heading_comes_first(self):
        out = build_gallery.font_links({"fonts": {"body": font("https://f/body"), "mono": font("https://f/mono"),
                                                  "heading": font("https://f/heading")}})
        self.assertEqual(out.splitlines()[0], '<link rel="stylesheet" href="https://f/heading">')
        self.assertEqual(out.count("<link"), 3)

    def test_a_shared_url_is_linked_once(self):
        out = build_gallery.font_links({"fonts": {"heading": font("https://f/same"), "body": font("https://f/same"),
                                                  "mono": font("https://f/mono")}})
        self.assertEqual(out.count("<link"), 2)

    def test_schema_3_sans_still_works(self):
        out = build_gallery.font_links({"fonts": {"sans": font("https://f/sans"), "mono": font("https://f/mono")}})
        self.assertEqual(out.count("<link"), 2)
        self.assertIn("https://f/sans", out)

    def test_no_fonts(self):
        self.assertEqual(build_gallery.font_links({}), "")


if __name__ == "__main__":
    unittest.main()
