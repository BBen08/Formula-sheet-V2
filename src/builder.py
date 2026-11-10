"""
builder.py - Turn the parsed Sheets into the web app.

It reads the files in src/templates/ (page.html, style.css, app.js, sw.js),
puts your formulas in as JSON, and writes everything to web/:

  web/index.html            the installable app (works offline, has the icon)
  web/sw.js                 the offline helper ("service worker")
  web/manifest.webmanifest  app name, icon and colours for the Home Screen
  web/icons/, web/vendor/   copied from src/static/ (icons and MathJax)
  web/publish.html          the same page for a claude.ai artifact: no
                            <html>/<body> wrapper, MathJax from the internet

web/ is the folder GitHub Pages publishes.
"""

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

from models import Sheet

SRC = Path(__file__).parent
TEMPLATES = SRC / "templates"
STATIC = SRC / "static"            # copied to web/ as-is

MATHJAX_LOCAL = "vendor/mathjax/tex-svg-full.js"
MATHJAX_CDN = "https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-svg-full.js"

# Extra <head> lines for the installable app (left out of publish.html).
# "noindex" asks Google and other search engines not to list the site, so
# only people who have the link find it. (It does not lock anyone out.)
APP_HEAD = """<meta name="robots" content="noindex, nofollow">
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" type="image/png" sizes="32x32" href="icons/favicon-32.png">
<link rel="apple-touch-icon" href="icons/apple-touch-icon.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Formulas">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="theme-color" content="#F3F5F1" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#10151B" media="(prefers-color-scheme: dark)">"""

FULL_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
{head}
</head>
<body>
{body}
</body>
</html>
"""
BODY_MARKER = "<!-- BODY -->"   # in page.html: splits <head> content from <body>


def build_data(sheets: list[Sheet], sources: list[str]) -> dict:
    sheet_dicts = [sheet.to_dict() for sheet in sheets]
    # Fingerprint of the formulas plus the app's own files, so the app can
    # tell whether a downloaded update really differs from what is on screen.
    content = hashlib.sha256(json.dumps(sheet_dicts, sort_keys=True).encode())
    for name in ("page.html", "style.css", "app.js"):
        content.update((TEMPLATES / name).read_bytes())
    return {
        "built": datetime.now().strftime("%d %b %Y, %H:%M"),
        "version": content.hexdigest()[:12],
        "sources": sources,
        "sheets": sheet_dicts,
    }


def render_page(data: dict, installable: bool) -> str:
    """Fill the placeholders in page.html and return the page as text."""
    page = (TEMPLATES / "page.html").read_text(encoding="utf-8")
    style = (TEMPLATES / "style.css").read_text(encoding="utf-8")
    app_js = (TEMPLATES / "app.js").read_text(encoding="utf-8")

    # "</" inside a <script> would end the script early, so escape it.
    data_json = json.dumps(data, ensure_ascii=False, indent=1).replace("</", "<\\/")

    return (page.replace("{{APP_HEAD}}", APP_HEAD if installable else "")
                .replace("{{MATHJAX_SRC}}", MATHJAX_LOCAL if installable else MATHJAX_CDN)
                .replace("{{STYLE}}", style)
                .replace("{{APP_JS}}", app_js)
                .replace("{{DATA}}", f"window.FORMULA_DATA = {data_json};"))


def write_service_worker(out_dir: Path) -> Path:
    """Write sw.js with the list of files to keep offline and a fingerprint."""
    files = sorted(
        p.relative_to(out_dir).as_posix()
        for p in out_dir.rglob("*")
        if p.is_file() and p.name not in ("sw.js", "publish.html", ".nojekyll", "LICENSE")
    )
    fingerprint = hashlib.sha256()
    for name in files:
        fingerprint.update(name.encode())
        fingerprint.update((out_dir / name).read_bytes())

    sw = (TEMPLATES / "sw.js").read_text(encoding="utf-8")
    sw = (sw.replace("{{VERSION}}", fingerprint.hexdigest()[:12])
            .replace("{{FILES}}", json.dumps(["./"] + files)))
    path = out_dir / "sw.js"
    path.write_text(sw, encoding="utf-8")
    return path


def write_site(sheets: list[Sheet], sources: list[str], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(STATIC, out_dir, dirs_exist_ok=True)
    (out_dir / ".nojekyll").touch()      # tells GitHub Pages to serve files as they are

    data = build_data(sheets, sources)
    index = out_dir / "index.html"
    publish = out_dir / "publish.html"
    head, body = render_page(data, installable=True).split(BODY_MARKER)
    index.write_text(FULL_PAGE.format(head=head.strip(), body=body.strip()), encoding="utf-8")
    publish.write_text(render_page(data, installable=False).replace(BODY_MARKER, ""), encoding="utf-8")
    return [index, publish, write_service_worker(out_dir)]
