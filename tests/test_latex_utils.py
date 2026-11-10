"""
Tests for latex_utils.py: does LaTeX turn into the HTML we expect?

Run all tests from the formula-app folder with:
    python -m unittest discover -s tests -v
or use the Testing panel (flask icon) in VS Code / Positron.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latex_utils import (  # noqa: E402
    extract_math, latex_to_html, latex_to_plain, match_brace, slugify, strip_comments,
)


class TestHelpers(unittest.TestCase):
    def test_strip_comments_keeps_escaped_percent(self):
        self.assertEqual(strip_comments("50\\% off % a comment"), "50\\% off ")

    def test_match_brace_handles_nesting(self):
        text = "{a{b}c}d"
        self.assertEqual(match_brace(text, 0), 6)

    def test_slugify(self):
        self.assertEqual(slugify("Integration by parts!"), "integration-by-parts")


class TestMath(unittest.TestCase):
    def test_inline_and_display_math_are_found(self):
        text, maths = extract_math(r"so $a+b$ and \[c=d\]")
        self.assertEqual(maths, [("inline", "a+b"), ("display", "c=d")])
        self.assertNotIn("$", text)

    def test_line_break_with_spacing_is_not_math(self):
        # "\\[2pt]" is a line break, not the start of display maths
        _, maths = extract_math(r"$x$\\[2pt]$y$")
        self.assertEqual([m[1] for m in maths], ["x", "y"])

    def test_math_is_escaped_for_html(self):
        self.assertIn(r"\(D&lt;0\)", latex_to_html("$D<0$", inline=True))


class TestText(unittest.TestCase):
    def test_bold_and_emphasis(self):
        out = latex_to_html(r"\textbf{bold} and \emph{em}", inline=True)
        self.assertEqual(out, "<strong>bold</strong> and <em>em</em>")

    def test_custom_macros(self):
        out = latex_to_html(r"\expl{Why} \warn{careful}")
        self.assertIn('<div class="expl">Why</div>', out)
        self.assertIn('<span class="warn"><b>!</b> careful</span>', out)

    def test_itemize(self):
        out = latex_to_html("\\begin{itemize}\n\\item one\n\\item two\n\\end{itemize}")
        self.assertIn("<ul><li>one</li><li>two</li></ul>", out)

    def test_tabular_with_math_and_header(self):
        src = "\\begin{tabular}{ll}\n a & b\\\\\\midrule\n $x$ & $y$\\\\\n\\end{tabular}"
        out = latex_to_html(src)
        self.assertIn("<th>a</th><th>b</th>", out)
        self.assertIn(r"<td>\(x\)</td>", out)

    def test_ampersand_in_text(self):
        self.assertEqual(latex_to_html(r"A \& B", inline=True), "A &amp; B")

    def test_unknown_commands_are_reported(self):
        unknown = set()
        latex_to_html(r"\fancything text", unknown=unknown)
        self.assertEqual(unknown, {"fancything"})

    def test_plain_text_keeps_math_names(self):
        plain = latex_to_plain(r"Derivative: $(\arcsin x)'=\frac{1}{\sqrt{1-x^2}}$")
        self.assertIn("arcsin", plain)
        self.assertNotIn("frac", plain)


if __name__ == "__main__":
    unittest.main()
