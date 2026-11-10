"""
builder.py - Build the V2 web app (the "shell": everything except the formulas).

It reads the files in src/templates/ (page.html, style.css, app.js, auth.js,
sw.js) and writes everything to web/:

  web/index.html            the installable app; shows the login screen and
                            downloads the formulas from Supabase after login
  web/sw.js                 the offline helper ("service worker")
  web/manifest.webmanifest  app name, icon and colours for the Home Screen
  web/icons/, web/vendor/   copied from src/static/ (icons, MathJax, supabase-js)

V2 never puts formulas in web/: they are only in the database (see
src/upload_cards.py). So web/ is safe to publish on GitHub Pages.
"""

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

SRC = Path(__file__).parent
TEMPLATES = SRC / "templates"
STATIC = SRC / "static"            # copied to web/ as-is

MATHJAX_LOCAL = "vendor/mathjax/tex-svg-full.js"

# The Supabase project of V2. Both values are public on purpose (they are in
# every page the browser loads); the database rules decide who sees what.
# NEVER put the secret key here: that one is only in the local .env file.
SUPABASE_URL = "https://hxlyqqacchkmzxohxywf.supabase.co"
SUPABASE_KEY = "sb_publishable_W1V8DzqsYmO77RFseHsFsw_xMYLo8jk"

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


def app_info() -> dict:
    """What the page needs to know before login (no formulas)."""
    fingerprint = hashlib.sha256((SUPABASE_URL + SUPABASE_KEY).encode())
    for name in ("page.html", "style.css", "app.js", "auth.js"):
        fingerprint.update((TEMPLATES / name).read_bytes())
    return {
        "built": datetime.now().strftime("%d %b %Y, %H:%M"),
        "version": fingerprint.hexdigest()[:12],
        "supabaseUrl": SUPABASE_URL,
        "supabaseKey": SUPABASE_KEY,
    }


def render_page(info: dict) -> str:
    """Fill the placeholders in page.html and return the page as text."""
    page = (TEMPLATES / "page.html").read_text(encoding="utf-8")
    style = (TEMPLATES / "style.css").read_text(encoding="utf-8")
    app_js = (TEMPLATES / "app.js").read_text(encoding="utf-8")
    auth_js = (TEMPLATES / "auth.js").read_text(encoding="utf-8")
    info_json = json.dumps(info, ensure_ascii=False, indent=1).replace("</", "<\\/")

    return (page.replace("{{APP_HEAD}}", APP_HEAD)
                .replace("{{MATHJAX_SRC}}", MATHJAX_LOCAL)
                .replace("{{STYLE}}", style)
                .replace("{{APP_JS}}", app_js)
                .replace("{{AUTH_JS}}", auth_js)
                .replace("{{DATA}}", f"window.FORMULA_APP = {info_json};"))


def write_service_worker(out_dir: Path) -> Path:
    """Write sw.js with the list of files to keep offline and a fingerprint."""
    files = sorted(
        p.relative_to(out_dir).as_posix()
        for p in out_dir.rglob("*")
        if p.is_file() and p.name not in ("sw.js", ".nojekyll", "LICENSE")
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


def write_site(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(STATIC, out_dir, dirs_exist_ok=True)
    (out_dir / ".nojekyll").touch()      # tells GitHub Pages to serve files as they are
    (out_dir / "publish.html").unlink(missing_ok=True)   # left over from the original app

    index = out_dir / "index.html"
    head, body = render_page(app_info()).split(BODY_MARKER)
    index.write_text(FULL_PAGE.format(head=head.strip(), body=body.strip()), encoding="utf-8")
    return [index, write_service_worker(out_dir)]
