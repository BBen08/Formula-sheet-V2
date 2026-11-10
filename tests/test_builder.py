"""
Tests for builder.py: is the installable page put together correctly?

iPhones only read the app icon, app name and "open full screen" setting from
the page's <head>. If they end up in <body>, the Home Screen icon becomes a
plain letter instead of the logo.
"""

import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
# V2 has no formulas of its own: it reads the original app's latex/ (read-only).
LATEX = ROOT.parent / "formula-app" / "latex"

from builder import write_site  # noqa: E402
from upload_cards import read_sheets  # noqa: E402


class TestInstallablePage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        out = Path(cls.tmp.name)
        write_site(out)
        cls.html = (out / "index.html").read_text(encoding="utf-8")
        cls.head, cls.body = cls.html.split("</head>")
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
        self.assertIn('id="gate"', self.body)            # the login screen
        self.assertIn("window.FORMULA_APP", self.body)
        self.assertIn("startFormulaApp", self.body)
        self.assertIn("window.FormulaOffline", self.body)   # offline copy (offline.js)
        self.assertIn('data-screen="offline-old"', self.body)
        self.assertIsNone(re.search(r"\{\{[A-Z_]+\}\}", self.html))   # every placeholder filled in

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
                     "vendor/mathjax/tex-svg-full.js", "vendor/supabase/supabase.js"]:
            self.assertTrue((self.out / name).is_file(), name)
        sw = (self.out / "sw.js").read_text(encoding="utf-8")
        self.assertIn("vendor/supabase/supabase.js", sw)


class TestNoFormulasInTheApp(unittest.TestCase):
    """V2 is published on GitHub: the built app must not contain the formulas."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name)
        write_site(cls.out)
        cls.files = {p.relative_to(cls.out).as_posix(): p.read_bytes()
                     for p in cls.out.rglob("*") if p.is_file()}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_no_formula_data_and_no_publish_page(self):
        self.assertNotIn("publish.html", self.files)
        self.assertNotIn(b"FORMULA_DATA", self.files["index.html"])

    def test_no_card_text_anywhere(self):
        if not LATEX.is_dir():
            self.skipTest("the original app's latex/ is not next to V2")
        cards = [c for s in read_sheets(LATEX) for sec in s.sections for c in sec.cards]
        own = [c.latex.encode() for c in cards if len(c.latex) > 40]
        self.assertGreater(len(own), 100)
        for name, data in self.files.items():
            if name.startswith("vendor/"):
                continue
            for snippet in own:
                self.assertNotIn(snippet, data, f"a formula ended up in {name}")

    def test_no_secret_key(self):
        # A real secret key looks like sb_secret_ + a long code. (supabase.js
        # contains the word "sb_secret_" in a warning, which is fine.)
        real_key = re.compile(rb"sb_secret_[A-Za-z0-9_-]{16,}")
        for name, data in self.files.items():
            self.assertIsNone(real_key.search(data), name)
        self.assertNotIn(b"service_role", self.files["index.html"])


if __name__ == "__main__":
    unittest.main()
