"""
Tests for upload_cards.py: are the database rows complete and in order?
These never connect to the internet.
"""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
# V2 has no formulas of its own: it reads the original app's latex/ (read-only).
LATEX = ROOT.parent / "formula-app" / "latex"

from upload_cards import card_rows, read_env, read_sheets  # noqa: E402


@unittest.skipUnless(LATEX.is_dir(), "needs ../formula-app/latex (not on GitHub, on purpose)")
class TestCardRows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sheets = read_sheets(LATEX)
        cls.rows = card_rows(cls.sheets, "2026-01-01T00:00:00+00:00")

    def test_every_card_becomes_one_row(self):
        expected = sum(sheet.card_count() for sheet in self.sheets)
        self.assertEqual(len(self.rows), expected)

    def test_positions_keep_the_app_order(self):
        self.assertEqual([r["position"] for r in self.rows], list(range(len(self.rows))))

    def test_rows_have_what_the_app_needs(self):
        for row in self.rows:
            for field in ("id", "tab", "tab_name", "chapter", "chapter_name", "section", "title_html", "body_html"):
                self.assertTrue(row[field], f"{row['id']} has no {field}")

    def test_no_local_file_paths_are_uploaded(self):
        here = str(LATEX.resolve().parent)
        for row in self.rows:
            for value in row.values():
                self.assertNotIn(here, str(value))
                self.assertNotIn(here.replace("\\", "/"), str(value))


class TestReadEnv(unittest.TestCase):
    def test_reads_keys_and_ignores_comments(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / ".env"
            env.write_text('# comment\nSUPABASE_URL=https://x.supabase.co\nSUPABASE_SECRET_KEY="abc"\n')
            self.assertEqual(read_env(env), {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SECRET_KEY": "abc"})

    def test_missing_file_is_empty(self):
        self.assertEqual(read_env(Path("does-not-exist.env")), {})


if __name__ == "__main__":
    unittest.main()
