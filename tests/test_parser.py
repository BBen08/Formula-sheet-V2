"""
Tests for tex_parser.py, using your real formula sheets in latex/.

If you change a .tex file a lot (rename a heading, remove a formula), a test
here can fail on purpose: update the expected names below to match.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
# V2 has no formulas of its own: it reads the original app's latex/ (read-only).
LATEX = ROOT.parent / "formula-app" / "latex"

from tex_parser import parse_sheet, split_by_named_formulas  # noqa: E402


def card_titles(sheet):
    return [card.title_text for section in sheet.sections for card in section.cards]


class TestNamedFormulaStyle(unittest.TestCase):
    def test_name_above_maths_starts_a_card(self):
        content = "Magnitude\n\\[A=\\sqrt{x}\\]\n\nDot Product\n\\[a\\cdot b\\]\n\\[=ab\\cos\\theta\\]"
        cards = split_by_named_formulas(content)
        self.assertEqual([t for t, _ in cards], ["Magnitude", "Dot Product"])
        self.assertIn("cos", cards[1][1])          # both lines stay in one card

    def test_maths_without_a_name_uses_section_title(self):
        cards = split_by_named_formulas("\\[M_O = Fd\\]")
        self.assertIsNone(cards[0][0])


@unittest.skipUnless(LATEX.is_dir(), "needs ../formula-app/latex (not on GitHub, on purpose)")
class TestCalculusSheet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.unknown = set()
        cls.sheet = parse_sheet("calculus", "Calculus", [LATEX / "math/00_calculus.tex"],
                                "#000000", cls.unknown)

    def test_sections_and_colours(self):
        names = [s.title_text for s in self.sheet.sections]
        self.assertEqual(names[0], "Basics")
        self.assertIn("Complex numbers", names)
        complex_numbers = self.sheet.sections[names.index("Complex numbers")]
        self.assertEqual(complex_numbers.color, "#8E44AD")    # from \definecolor{cCplx}

    def test_every_sub_heading_is_a_card(self):
        titles = card_titles(self.sheet)
        for expected in ["Integration by parts", "Substitution", "Polar form",
                         "Implicit differentiation", "Standard Maclaurin a 0"]:
            self.assertIn(expected, titles)

    def test_explanation_only_intro_is_not_a_card(self):
        basics = self.sheet.sections[0]
        self.assertIn("expl", basics.intro_html)
        self.assertEqual(basics.cards[0].title_text, "Derivative rules")

    def test_no_unknown_commands(self):
        self.assertEqual(self.unknown, set())


@unittest.skipUnless(LATEX.is_dir(), "needs ../formula-app/latex (not on GitHub, on purpose)")
class TestStaticsSheet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.unknown = set()
        cls.sheet = parse_sheet("statics", "Statics", [LATEX / "physics/00_statics.tex"],
                                "#1F6FB2", cls.unknown)

    def test_named_formulas_are_cards(self):
        titles = card_titles(self.sheet)
        for expected in ["Dot Product", "Cross Product", "Buoyancy Archimedes",
                         "Static Coulomb friction", "Rolling resistance"]:
            self.assertIn(expected, titles)

    def test_cross_product_keeps_both_formulas(self):
        card = next(c for s in self.sheet.sections for c in s.cards if c.title_text == "Cross Product")
        self.assertEqual(card.body_html.count("\\["), 2)

    def test_table_and_list_sections_become_one_card(self):
        titles = card_titles(self.sheet)
        self.assertIn("SI-Units", titles)
        self.assertIn("FBD or Free Body Diagrams", titles)

    def test_no_unknown_commands(self):
        self.assertEqual(self.unknown, set())


@unittest.skipUnless(LATEX.is_dir(), "needs ../formula-app/latex (not on GitHub, on purpose)")
class TestChapters(unittest.TestCase):
    """Each folder in latex/ is a tab; each .tex file in it is a chapter."""

    @classmethod
    def setUpClass(cls):
        cls.sheets = {}
        for folder in ("math", "physics"):
            unknown = set()
            files = sorted((LATEX / folder).glob("*.tex"))
            cls.sheets[folder] = parse_sheet(folder, folder.title(), files, "#000000", unknown)
            cls.sheets[folder].unknown = unknown

    def test_course_sheets_are_the_first_chapter(self):
        self.assertEqual(self.sheets["math"].chapters[0].name, "Calculus")
        self.assertEqual(self.sheets["physics"].chapters[0].name, "Statics")

    def test_one_section_chapters_keep_their_full_title(self):
        names = [c.name for c in self.sheets["math"].chapters]
        self.assertIn("Functions, Sequences & Limits", names)   # comma and & kept

    def test_every_section_belongs_to_a_chapter(self):
        for sheet in self.sheets.values():
            ids = {c.id for c in sheet.chapters}
            for section in sheet.sections:
                self.assertIn(section.chapter, ids, section.title_text)

    def test_card_ids_are_unique_within_a_tab(self):
        for sheet in self.sheets.values():
            ids = [card.id for s in sheet.sections for card in s.cards]
            self.assertEqual(len(ids), len(set(ids)))

    def test_no_unknown_commands(self):
        for sheet in self.sheets.values():
            self.assertEqual(sheet.unknown, set(), sheet.name)


if __name__ == "__main__":
    unittest.main()
