"""
Tests for builder.py: is the installable page put together correctly?

iPhones only read the app icon, app name and "open full screen" setting from
the page's <head>. If they end up in <body>, the Home Screen icon becomes a
plain letter instead of the logo.
"""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
# V2 has no formulas of its own: it reads the original app's latex/ (read-only).
LATEX = ROOT.parent / "formula-app" / "latex"

from builder import write_site  # noqa: E402
from tex_parser import parse_sheet  # noqa: E402


class TestInstallablePage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sheet = parse_sheet("statics", "Statics", [LATEX / "physics/00_statics.tex"], "#1F6FB2")
        cls.tmp = tempfile.TemporaryDirectory()
        out = Path(cls.tmp.name)
        write_site([sheet], ["statics/main.tex"], out)
        html = (out / "index.html").read_text(encoding="utf-8")
        cls.head, cls.body = html.split("</head>")
        cls.publish = (out / "publish.html").read_text(encoding="utf-8")
        cls.out = out

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_icon_and_app_settings_are_in_head(self):
        for tag in ['<link rel="apple-touch-icon"', '<link rel="manifest"',
                    '<meta name="apple-mobile-web-app-capable"', "<title>", '<meta name="robots"']:
            self.assertIn(tag, self.head, f"{tag} must be in <head>")
            self.assertNotIn(tag, self.body)

    def test_app_content_is_in_body(self):
        self.assertIn('id="list"', self.body)
        self.assertIn("window.FORMULA_DATA", self.body)

    def test_info_button_and_panel(self):
        self.assertIn('id="info-btn"', self.body)
        self.assertIn('<dialog class="info" id="info"', self.body)
        self.assertIn("What this app does", self.body)
        self.assertIn("How to install it", self.body)
        self.assertIn("© 2026 Benjamin Bek. All rights reserved.", self.body)
        self.assertIn("For personal study use only.", self.body)
        for choice in ("auto", "light", "dark"):
            self.assertIn(f'data-theme-choice="{choice}"', self.body)
        self.assertIn('id="owner-msg"', self.body)
        self.assertNotIn("to copy its LaTeX", self.body)

    def test_signature_logo(self):
        self.assertIn('src="icons/logo-navy.png"', self.body)
        self.assertIn('src="icons/logo-pale.png"', self.body)
        sw = (self.out / "sw.js").read_text(encoding="utf-8")
        self.assertIn("icons/logo-navy.png", sw)
        self.assertIn("icons/logo-pale.png", sw)

    def test_offline_files_exist(self):
        for name in ["sw.js", "manifest.webmanifest", "icons/apple-touch-icon.png",
                     "vendor/mathjax/tex-svg-full.js"]:
            self.assertTrue((self.out / name).is_file(), name)

    def test_publish_version_has_no_app_install_tags(self):
        self.assertNotIn('<link rel="manifest"', self.publish)
        self.assertNotIn("<!-- BODY -->", self.publish)


if __name__ == "__main__":
    unittest.main()
