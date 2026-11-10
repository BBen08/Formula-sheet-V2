"""
upload_cards.py - Put your formulas in the V2 database (Supabase).

    python src/upload_cards.py --dry-run   read the .tex files, check, upload nothing
    python src/upload_cards.py             read the .tex files and upload all cards

It reads the .tex files (read-only) from ../formula-app/latex, turns them into
cards exactly like the app does, and sends them to the `cards` table. Cards
that no longer exist in your .tex files are removed from the database.

It needs the SECRET key of your Supabase project, which may never be in git.
Put it in the file `.env` in the formula-app-v2 folder (git ignores that file):

    SUPABASE_URL=https://xxxx.supabase.co
    SUPABASE_SECRET_KEY=sb_secret_...
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from main import LATEX, PROJECT, SHEET_COLORS, find_sheets, pretty_name
from models import Sheet
from tex_parser import parse_sheet

ENV_FILE = PROJECT / ".env"
BATCH = 100          # cards per request


def read_sheets(latex_dir: Path) -> list[Sheet]:
    sheets = []
    for i, (name, tex_files) in enumerate(find_sheets(latex_dir)):
        sheets.append(parse_sheet(name.lower(), pretty_name(name), tex_files,
                                  SHEET_COLORS[i % len(SHEET_COLORS)]))
    return sheets


def card_rows(sheets: list[Sheet], uploaded_at: str) -> list[dict]:
    """One database row per card, in the order the app shows them."""
    rows = []
    for sheet in sheets:
        chapters = {c.id: c for c in sheet.chapters}
        for section in sheet.sections:
            chapter = chapters.get(section.chapter)
            for card in section.cards:
                rows.append({
                    "id": card.id,
                    "position": len(rows),
                    "tab": sheet.id,
                    "tab_name": sheet.name,
                    "tab_title": sheet.title,
                    "chapter": section.chapter,
                    "chapter_name": chapter.name if chapter else "",
                    "chapter_source": chapter.source if chapter else "",
                    "section": section.id,
                    "section_title_html": section.title_html,
                    "section_title_text": section.title_text,
                    "section_color": section.color,
                    "section_intro_html": section.intro_html,
                    "title_html": card.title_html,
                    "title_text": card.title_text,
                    "body_html": card.body_html,
                    "body_text": card.body_text,
                    "latex": card.latex,
                    "uploaded_at": uploaded_at,
                })
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Two cards have the same id; rename one of the headings.")
    return rows


def read_env(path: Path) -> dict:
    env = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def request(method: str, url: str, key: str, body=None, prefer: str = "") -> int:
    headers = {"apikey": key, "Content-Type": "application/json"}
    if key.startswith("eyJ"):                 # old-style (legacy) service_role key
        headers["Authorization"] = "Bearer " + key
    if prefer:
        headers["Prefer"] = prefer
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as response:
        return response.status


def upload(rows: list[dict], base_url: str, key: str, uploaded_at: str) -> None:
    table = base_url.rstrip("/") + "/rest/v1/cards"
    for start in range(0, len(rows), BATCH):
        request("POST", table + "?on_conflict=id", key, rows[start:start + BATCH],
                prefer="resolution=merge-duplicates,return=minimal")
        print(f"  uploaded {min(start + BATCH, len(rows))}/{len(rows)}")
    # Everything not touched by this upload is a card you removed from LaTeX.
    stamp = urllib.request.quote(uploaded_at, safe="")
    request("DELETE", f"{table}?uploaded_at=lt.{stamp}", key, prefer="return=minimal")
    print("  removed cards that are no longer in your .tex files")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Upload the formula cards to Supabase.")
    parser.add_argument("--latex", type=Path, default=LATEX, help="folder with your .tex files")
    parser.add_argument("--dry-run", action="store_true", help="check everything, upload nothing")
    args = parser.parse_args(argv)

    print(f"Reading {args.latex.resolve()}")
    uploaded_at = datetime.now(timezone.utc).isoformat()
    rows = card_rows(read_sheets(args.latex), uploaded_at)
    tabs = {}
    for r in rows:
        tabs[r["tab_name"]] = tabs.get(r["tab_name"], 0) + 1
    print("  " + ", ".join(f"{name}: {n} cards" for name, n in tabs.items()) + f"  (total {len(rows)})")
    if args.dry_run:
        print("Dry run: nothing was uploaded.")
        return 0

    env = read_env(ENV_FILE)
    url, key = env.get("SUPABASE_URL", ""), env.get("SUPABASE_SECRET_KEY", "")
    if not url.startswith("https://") or not key or "paste" in key:
        print(f"Missing SUPABASE_URL or SUPABASE_SECRET_KEY in {ENV_FILE}")
        return 1
    if key.startswith("sb_publishable_"):
        print("That is the publishable key; the upload needs the SECRET key (sb_secret_...).")
        return 1
    try:
        upload(rows, url, key, uploaded_at)
    except urllib.error.HTTPError as err:
        print(f"Upload failed: HTTP {err.code} {err.read().decode('utf-8', 'replace')[:300]}")
        return 1
    except urllib.error.URLError as err:
        print(f"Upload failed: {err.reason}. Check your internet connection.")
        return 1
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
