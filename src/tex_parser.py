"""
tex_parser.py - Read a folder of .tex files and split it into Chapters,
Sections and Cards.

Each .tex file becomes one Chapter (see chapter_name() for its label).

How a document is cut into searchable cards
-------------------------------------------
1. Everything between \\begin{document} and \\end{document} is read.
2. A new SECTION starts at every  \\section{Title}  or  \\sect{colour}{Title}
   (\\sect is the coloured heading macro from the Calculus sheet).
3. Inside a section there are two styles, and the parser picks per section:

   a) Sub-heading style (Calculus):
        \\sub{Integration by parts}      <- each \\sub (or \\subsection)
        ...formulas and text...             starts a new card
      Text before the first \\sub becomes the section's intro if it is only
      an \\expl{...}, otherwise it becomes a card named after the section.

   b) Named-formula style (Statics):
        Dot Product                      <- a short line of text directly
        \\[ A \\cdot B = ... \\]               above display maths is the name
      Several \\[...\\] in a row without a new name stay in one card.
      A section without any \\[...\\] becomes one card.

If a formula ends up in the wrong card, the rules above are where to look.
"""

import html
import re
from pathlib import Path

from latex_utils import (
    latex_to_html, latex_to_plain, read_group, slugify, strip_comments,
)
from models import Card, Chapter, Section, Sheet

SECTION_RE = re.compile(r"\\(section|sect)(?![a-zA-Z])\*?")
SUB_RE = re.compile(r"\\(sub|subsection|subsubsection)(?![a-zA-Z])\*?")
DISPLAY_MATH_RE = re.compile(r"(?<!\\)\\\[.*?\\\]", re.S)
COLOR_RE = re.compile(r"\\definecolor\{(\w+)\}\{HTML\}\{([0-9A-Fa-f]{6})\}")

# A line of text this short (and on one line) right above \[...\] is a name.
MAX_NAME_LENGTH = 120


# ---------------------------------------------------------------------------
# Reading the whole document
# ---------------------------------------------------------------------------
def read_document(path: Path):
    """Return (title, colours, body) of a .tex file, with comments removed."""
    raw = strip_comments(path.read_text(encoding="utf-8"))
    colors = {name: "#" + hex_.upper() for name, hex_ in COLOR_RE.findall(raw)}

    title = None
    m = re.search(r"\\title\{", raw)
    if m:
        title, _ = read_group(raw, m.end() - 1)
    else:
        m = re.search(r"\{\\(?:Large|LARGE|huge)\\bfseries\s*([^{}]*)\}", raw)
        if m:
            title = m.group(1)
    title = latex_to_plain(title) if title else path.stem

    start = raw.find("\\begin{document}")
    end = raw.rfind("\\end{document}")
    body = raw[start + len("\\begin{document}"):end if end != -1 else None] if start != -1 else raw
    return title, colors, body


def split_sections(body: str):
    """Yield (title_latex, colour_name_or_None, content) for every section."""
    matches = list(SECTION_RE.finditer(body))
    for k, m in enumerate(matches):
        pos = m.end()
        color_name = None
        if m.group(1) == "sect":            # \sect{colour}{title}
            color_name, pos = read_group(body, pos)
        title, pos = read_group(body, pos)
        if title is None:
            continue
        stop = matches[k + 1].start() if k + 1 < len(matches) else len(body)
        yield title, color_name, body[pos:stop]


# ---------------------------------------------------------------------------
# Cutting one section into cards
# ---------------------------------------------------------------------------
def _only_explanations(text: str) -> bool:
    """True when `text` contains nothing but \\expl{...} blocks."""
    rest = text
    while (m := re.search(r"\\expl\{", rest)):
        _, after = read_group(rest, m.end() - 1)
        rest = rest[:m.start()] + rest[after:]
    return not rest.strip()


def split_by_subheadings(content: str):
    """Sub-heading style. Returns (intro_latex, [(title_latex, body_latex)])."""
    matches = list(SUB_RE.finditer(content))
    intro = content[:matches[0].start()] if matches else content
    pieces = []
    for k, m in enumerate(matches):
        title, pos = read_group(content, m.end())
        stop = matches[k + 1].start() if k + 1 < len(matches) else len(content)
        pieces.append((title or "", content[pos:stop]))
    return intro, pieces


def _is_name(text: str) -> bool:
    return ("\n" not in text and len(text) <= MAX_NAME_LENGTH
            and "\\begin" not in text and "\\item" not in text)


def split_by_named_formulas(content: str):
    """Named-formula style. Returns [(title_latex_or_None, body_latex)].

    A title of None means "use the section title"."""
    cards = []                               # list of [title, [body parts]]
    pos = 0
    for m in DISPLAY_MATH_RE.finditer(content):
        text = content[pos:m.start()].strip()
        if text and _is_name(text):
            cards.append([text, []])         # a name above the maths: new card
        elif text:
            if not cards:
                cards.append([None, []])
            cards[-1][1].append(text)        # longer text: belongs to this card
        elif not cards:
            cards.append([None, []])
        cards[-1][1].append(m.group(0))
        pos = m.end()

    trailing = content[pos:].strip()
    if trailing:
        if cards:
            cards[-1][1].append(trailing)   # e.g. "Where r represents ..."
        else:
            cards.append([None, [trailing]])
    return [(title, "\n\n".join(parts)) for title, parts in cards]


# ---------------------------------------------------------------------------
# Building the Sheet
# ---------------------------------------------------------------------------
def _clean_section_title(title: str) -> str:
    return re.sub(r"^\s*\d+\.\s*", "", title)   # "2. Integration" -> "Integration"


def parse_sheet(sheet_id: str, name: str, tex_files: list[Path],
                default_color: str, unknown: set | None = None) -> Sheet:
    """Parse one or more .tex files into a single Sheet (one tab in the app)."""
    titles = []
    sheet = Sheet(id=sheet_id, name=name, title="",
                  source=", ".join(str(p) for p in tex_files))
    used_ids: set[str] = set()

    def unique_id(*parts: str) -> str:
        base = slugify("-".join(parts))
        new, n = base, 2
        while new in used_ids:
            new, n = f"{base}-{n}", n + 1
        used_ids.add(new)
        return new

    def make_card(section: Section, title_latex: str, body_latex: str) -> Card:
        title_plain = latex_to_plain(title_latex)
        return Card(
            id=unique_id(sheet_id, section.title_text, title_plain),
            title_html=latex_to_html(title_latex, inline=True, unknown=unknown),
            title_text=title_plain,
            body_html=latex_to_html(body_latex, unknown=unknown),
            body_text=latex_to_plain(body_latex),
            latex=body_latex.strip(),
        )

    for path in tex_files:
        title, colors, body = read_document(path)
        titles.append(title)
        first_section = len(sheet.sections)
        for raw_title, color_name, content in split_sections(body):
            raw_title = _clean_section_title(raw_title)
            section = Section(
                id=unique_id(sheet_id, "section", latex_to_plain(raw_title)),
                title_html=latex_to_html(raw_title, inline=True, unknown=unknown),
                title_text=latex_to_plain(raw_title),
                color=colors.get(color_name or "", default_color),
            )

            if SUB_RE.search(content):                       # style a)
                intro, pieces = split_by_subheadings(content)
                if intro.strip() and _only_explanations(intro):
                    section.intro_html = latex_to_html(intro, unknown=unknown)
                elif intro.strip():
                    pieces.insert(0, (raw_title, intro))
            else:                                            # style b)
                pieces = [(t if t is not None else raw_title, b)
                          for t, b in split_by_named_formulas(content)]

            for title_latex, body_latex in pieces:
                if body_latex.strip():
                    section.cards.append(make_card(section, title_latex, body_latex))
            if section.cards:
                sheet.sections.append(section)

        # Every .tex file is one chapter (one chapter button in the app).
        file_sections = sheet.sections[first_section:]
        if file_sections:
            name_ = chapter_name(path, file_sections)
            chapter = Chapter(id=unique_id(sheet_id, "chapter", name_), name=name_,
                              source=f"{path.parent.name}/{path.name}")
            sheet.chapters.append(chapter)
            for section in file_sections:
                section.chapter = chapter.id

    sheet.title = " + ".join(titles)
    return sheet


def chapter_name(path: Path, sections: list[Section]) -> str:
    """The label of a chapter button.

    A file with one section is named after that section, e.g.
    "Algebra & Complex Numbers". A file with several sections is named after
    the file, without a number in front: "00_calculus.tex" -> "Calculus".
    (A file called main.tex is named after its folder instead.)"""
    if len(sections) == 1:   # the display title, with HTML tags removed
        return html.unescape(re.sub(r"<[^>]+>", "", sections[0].title_html)).strip()
    stem = path.parent.name if path.stem.lower() == "main" else path.stem
    stem = re.sub(r"^\d+[_\-\s]*", "", stem)
    return stem.replace("_", " ").replace("-", " ").strip().title() or path.stem
