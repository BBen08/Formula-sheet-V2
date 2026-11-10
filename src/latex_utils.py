"""
latex_utils.py - Small tools for turning pieces of LaTeX into HTML.

The web page uses MathJax to draw the maths, so we do NOT convert maths
ourselves. We only:
  1. cut the maths out ($...$ and \\[...\\]) and keep it untouched,
  2. convert the text around it (\\textbf, itemize, tabular, ...) to HTML,
  3. put the maths back, written as \\( ... \\) and \\[ ... \\] for MathJax.

If a LaTeX command shows up wrong on the web page, this is the file to edit.
The most useful places:
  - TEXT_SYMBOLS        text-mode commands that become a character (\\mu -> μ)
  - IGNORED_COMMANDS    layout commands that are simply removed (\\noindent, ...)
  - _convert_commands() commands with an argument (\\textbf{...}, \\warn{...}, ...)
  - _convert_environments()  itemize / enumerate / tabular / center
"""

import html
import re
import unicodedata

# ---------------------------------------------------------------------------
# Placeholders.
# While converting, special characters are swapped for tokens that cannot
# appear in normal text (\x01...\x01). This stops, for example, a "<" in your
# text from being read as the start of an HTML tag. They are swapped back at
# the very end.
# ---------------------------------------------------------------------------
AMP = "\x01amp\x01"
LT = "\x01lt\x01"
GT = "\x01gt\x01"


def _math_token(index: int) -> str:
    return f"\x00M{index}\x00"


MATH_TOKEN_RE = re.compile(r"\x00M(\d+)\x00")

# Text-mode commands that are replaced by one character.
TEXT_SYMBOLS = {
    "mu": "μ", "alpha": "α", "beta": "β", "gamma": "γ", "theta": "θ",
    "rho": "ρ", "pi": "π", "Sigma": "Σ", "Delta": "Δ", "omega": "ω",
    "rightarrow": "→", "Rightarrow": "⇒", "leftarrow": "←",
    "Leftrightarrow": "⇔", "times": "×", "pm": "±", "degree": "°",
    "ldots": "…", "dots": "…", "LaTeX": "LaTeX", "TeX": "TeX",
}

# Layout commands without an argument that mean nothing on a web page.
IGNORED_COMMANDS = {
    "noindent", "par", "small", "footnotesize", "normalsize", "large",
    "Large", "LARGE", "raggedcolumns", "newpage", "clearpage", "centering",
    "maketitle", "tableofcontents", "hline", "medskip", "bigskip",
    "smallskip", "bfseries", "itshape", "raggedright", "linebreak",
    "toprule", "midrule", "bottomrule",
}

# Environments we drop the arguments of, and how many arguments they take.
ENV_ARG_COUNT = {"multicols": 1, "minipage": 1}


# ---------------------------------------------------------------------------
# Basic helpers
# ---------------------------------------------------------------------------
def strip_comments(text: str) -> str:
    """Remove everything after an unescaped % on every line."""
    return re.sub(r"(?<!\\)%.*", "", text)


def match_brace(text: str, open_index: int) -> int:
    """Given the index of a '{', return the index of its matching '}'.

    Returns -1 if the braces are unbalanced."""
    depth = 0
    i = open_index
    while i < len(text):
        ch = text[i]
        if ch == "\\":          # skip escaped characters like \{ and \}
            i += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def read_group(text: str, pos: int):
    """Read one {argument} starting at or after `pos` (spaces allowed).

    Returns (content, index_after_closing_brace), or (None, pos) when there
    is no {argument} there."""
    i = pos
    while i < len(text) and text[i] in " \t":
        i += 1
    if i >= len(text) or text[i] != "{":
        return None, pos
    end = match_brace(text, i)
    if end == -1:
        return None, pos
    return text[i + 1:end], end + 1


def slugify(text: str) -> str:
    """'Integration by parts!' -> 'integration-by-parts'"""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "item"


# ---------------------------------------------------------------------------
# Step 1: cut the maths out
# ---------------------------------------------------------------------------
def extract_math(text: str):
    """Replace every $...$, \\(...\\) and \\[...\\] by a placeholder token.

    Returns (text_with_tokens, maths) where maths is a list of
    ("inline" | "display", latex_source)."""
    out, maths = [], []
    i, n = 0, len(text)

    def add(kind, source):
        maths.append((kind, source))
        out.append(_math_token(len(maths) - 1))

    while i < n:
        ch = text[i]
        if ch == "\\" and i + 1 < n:
            nxt = text[i + 1]
            if nxt in "[(":
                closing = "\\]" if nxt == "[" else "\\)"
                end = text.find(closing, i + 2)
                if end != -1:
                    add("display" if nxt == "[" else "inline", text[i + 2:end])
                    i = end + 2
                    continue
            # Any other backslash pair (\\, \$, \&, \[ without end) is copied
            # as-is. Copying "\\" as a pair is what stops "\\[2pt]" (a line
            # break) from being mistaken for display maths.
            out.append(text[i:i + 2])
            i += 2
            continue
        if ch == "$":
            display = text.startswith("$$", i)
            start = i + (2 if display else 1)
            j = start
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == "$":
                    break
                j += 1
            if j < n:
                add("display" if display else "inline", text[start:j])
                i = j + (2 if display else 1)
                continue
        out.append(ch)
        i += 1
    return "".join(out), maths


def _math_to_html(kind: str, source: str) -> str:
    source = html.escape(source.strip(), quote=False)
    if kind == "display":
        return f"\\[{source}\\]"
    return f"\\({source}\\)"


# ---------------------------------------------------------------------------
# Step 2: convert the text around the maths
# ---------------------------------------------------------------------------
def _remove_layout_commands(text: str) -> str:
    text = re.sub(r"\\renewcommand\{\\\w+\}\{[^{}]*\}", "", text)
    text = re.sub(r"\\setlength\{\\\w+\}\{[^{}]*\}", "", text)
    text = re.sub(r"\\[vh]space\*?\{[^{}]*\}", " ", text)
    text = re.sub(r"\\color\{[^{}]*\}", "", text)
    return text


def _split_table_rows(body: str):
    rows = re.split(r"\\\\(?:\[[^\]]*\])?", body)
    clean = []
    for row in rows:
        row = re.sub(r"\\(hline|toprule|midrule|bottomrule)\b", "", row)
        row = re.sub(r"\\cline\{[^}]*\}", "", row)
        if row.strip():
            clean.append([cell.strip() for cell in row.split("&")])
    return clean


def _table_to_html(body: str) -> str:
    rows = _split_table_rows(body)
    if not rows:
        return ""
    has_header = bool(re.search(r"\\(midrule|toprule)\b", body)) or all(
        c.startswith("\\textit") for c in rows[0] if c
    )
    parts = ['<div class="table-wrap"><table>']
    for r, row in enumerate(rows):
        tag = "th" if (has_header and r == 0) else "td"
        cells = "".join(f"<{tag}>{cell}</{tag}>" for cell in row)
        parts.append(f"<tr>{cells}</tr>")
    parts.append("</table></div>")
    return "".join(parts)


def _list_to_html(body: str, ordered: bool) -> str:
    items = re.split(r"\\item\b(?:\[[^\]]*\])?", body)[1:]
    tag = "ol" if ordered else "ul"
    lis = "".join(f"<li>{item.strip()}</li>" for item in items if item.strip())
    return f"<{tag}>{lis}</{tag}>"


def _convert_environments(text: str) -> str:
    r"""Convert \begin{...}...\end{...} blocks, innermost first."""
    begin_re = re.compile(r"\\begin\{(\w+\*?)\}")
    while True:
        begins = list(begin_re.finditer(text))
        if not begins:
            return text
        m = begins[-1]                      # the last \begin is never nested further
        name = m.group(1)
        end_tag = f"\\end{{{name}}}"
        end = text.find(end_tag, m.end())
        if end == -1:                       # unbalanced: drop the \begin and move on
            text = text[:m.start()] + text[m.end():]
            continue
        pos = m.end()
        # skip arguments: tabular{spec}, tabularx{width}{spec}, multicols{2}
        n_args = {"tabular": 1, "tabularx": 2, "array": 1}.get(name, ENV_ARG_COUNT.get(name, 0))
        while True:                          # optional [position] argument
            opt = re.match(r"\s*\[[^\]]*\]", text[pos:])
            if not opt:
                break
            pos += opt.end()
        for _ in range(n_args):
            _, pos = read_group(text, pos)
        body = re.sub(r"\n\s*\n", "\n", text[pos:end])  # no blank lines inside blocks

        if name in ("tabular", "tabularx", "array"):
            replacement = _table_to_html(body)
        elif name in ("itemize", "enumerate"):
            replacement = _list_to_html(body, ordered=(name == "enumerate"))
        elif name in ("center", "flushleft", "flushright"):
            replacement = f'<div class="center">{body}</div>'
        else:                               # unknown environment: keep its content
            replacement = body
        text = text[:m.start()] + replacement + text[end + len(end_tag):]


# Commands with one {argument}: name -> (html_before, html_after)
WRAP_COMMANDS = {
    "textbf": ("<strong>", "</strong>"),
    "textit": ("<em>", "</em>"),
    "emph": ("<em>", "</em>"),
    "underline": ("<u>", "</u>"),
    "text": ("", ""),
    "mbox": ("", ""),
    "textrm": ("", ""),
    "textsuperscript": ("<sup>", "</sup>"),
    "textsubscript": ("<sub>", "</sub>"),
    # The custom macros from the Calculus sheet:
    "expl": ('<div class="expl">', "</div>"),
    "warn": ('<span class="warn"><b>!</b> ', "</span>"),
    "sub": ('<strong class="subhead">', "</strong>"),
}


def _convert_commands(text: str) -> str:
    pattern = re.compile(r"\\(" + "|".join(WRAP_COMMANDS) + r")(?![a-zA-Z])\*?")
    pos = 0
    while True:
        m = pattern.search(text, pos)
        if not m:
            return text
        arg, after = read_group(text, m.end())
        if arg is None:                     # command without {argument}: leave it
            pos = m.end()
            continue
        before_html, after_html = WRAP_COMMANDS[m.group(1)]
        text = text[:m.start()] + before_html + arg + after_html + text[after:]
        pos = m.start()                     # search again here: handles nesting


def _convert_symbols(text: str, unknown) -> str:
    text = text.replace("---", "—").replace("--", "–")
    text = text.replace("``", "“").replace("''", "”")
    text = re.sub(r"\\\\(?:\[[^\]]*\])?", "<br>", text)     # \\ and \\[2pt]
    text = re.sub(r"\\qquad\b", "&emsp;&emsp;", text)
    text = re.sub(r"\\quad\b", "&emsp;", text)
    text = re.sub(r"\\[ ,;:!]", " ", text)                  # \  \, \; ...
    text = text.replace("~", "&nbsp;")

    def command(m):
        name = m.group(1)
        if name in TEXT_SYMBOLS:
            return TEXT_SYMBOLS[name]
        if name not in IGNORED_COMMANDS and unknown is not None:
            unknown.add(name)
        return ""

    text = re.sub(r"\\([a-zA-Z]+)\*?\s?", command, text)
    return text.replace("{", "").replace("}", "")           # leftover grouping braces


def _paragraphs(text: str, inline: bool) -> str:
    # A <br> next to a block element only adds empty space.
    block = r"(?:</?(?:div|ul|ol|li|table)\b[^>]*>)"
    text = re.sub(r"(?:\s*<br>)+\s*(?=" + block + ")", "", text)
    text = re.sub(r"(" + block + r")(?:\s*<br>)+", r"\1", text)

    if inline:
        return re.sub(r"\s+", " ", text).strip()
    paras = []
    for chunk in re.split(r"\n\s*\n", text):
        chunk = re.sub(r"\s+", " ", chunk).strip()
        chunk = re.sub(r"^(?:<br>\s*)+|(?:\s*<br>)+$", "", chunk)
        if chunk:
            paras.append(f'<div class="para">{chunk}</div>')
    return "\n".join(paras)


# ---------------------------------------------------------------------------
# The public functions
# ---------------------------------------------------------------------------
def latex_to_html(source: str, inline: bool = False, unknown: set | None = None) -> str:
    """Convert a piece of LaTeX (text + maths) to HTML for the web page.

    inline=True gives one line without paragraph <div>s (for titles).
    Commands we do not know are removed and their names added to `unknown`,
    so main.py can warn you about them."""
    text = strip_comments(source)
    text, maths = extract_math(text)

    text = text.replace("\\&", AMP).replace("\\%", "%").replace("\\$", "$")
    text = text.replace("\\_", "_").replace("\\#", "#")
    text = text.replace("<", LT).replace(">", GT)

    text = _remove_layout_commands(text)
    text = _convert_environments(text)      # uses & as table separator...
    text = re.sub(r"\\(begin|end)\{[^{}]*\}", "", text)   # unmatched leftovers
    text = text.replace("&", AMP)           # ...so only now escape the rest
    text = _convert_commands(text)
    text = _convert_symbols(text, unknown)
    text = _paragraphs(text, inline)

    text = text.replace(AMP, "&amp;").replace(LT, "&lt;").replace(GT, "&gt;")
    return MATH_TOKEN_RE.sub(lambda m: _math_to_html(*maths[int(m.group(1))]), text)


# Formatting commands that are useless as search words.
_SEARCH_STOP = {
    "frac", "dfrac", "tfrac", "displaystyle", "left", "right", "big", "Big",
    "bigg", "quad", "qquad", "text", "mathrm", "mathbb", "hat", "vec", "bar",
    "tilde", "cdot", "cdots", "dots", "ldots", "underbrace", "begin", "end",
    "vmatrix", "imath", "jmath", "mathbf", "operatorname", "sqrt",
}


def latex_to_plain(source: str) -> str:
    """Plain lowercase-friendly text used for searching.

    Maths is kept as words, so searching 'arcsin' or 'sum' still finds
    formulas that only contain \\arcsin or \\sum."""
    text = latex_to_html(source, inline=True)

    def math_words(m):
        words = re.sub(r"\\([a-zA-Z]+)",
                       lambda w: "" if w.group(1) in _SEARCH_STOP else f" {w.group(1)} ",
                       html.unescape(m.group(1)))
        return " " + words + " "

    text = re.sub(r"\\[\(\[](.*?)\\[\)\]]", math_words, text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[^\w\s\-'’&]", " ", text)
    return re.sub(r"\s+", " ", text).strip()
