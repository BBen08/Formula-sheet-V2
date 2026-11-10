"""
main.py - Run this file to (re)build the Formula Finder app.

    python src/main.py            build web/index.html from latex/
    python src/main.py --serve    build, then open it at http://localhost:8000
    python src/main.py --serve --lan
                                  also reachable from your phone on the same Wi-Fi
    python src/main.py --publish  test, build, then commit + push to GitHub,
                                  which updates the app on your phone

How your LaTeX files are found
------------------------------
Every folder inside latex/ becomes one tab in the app, named after the folder:

    latex/calculus/main.tex   ->  tab "Calculus"
    latex/statics/main.tex    ->  tab "Statics"

A .tex file placed directly in latex/ becomes a tab named after the file.
To add a new course: make a folder in latex/, put the .tex file in it, run this.
"""

import argparse
import functools
import http.server
import socket
import subprocess
import sys
import webbrowser
from pathlib import Path

from builder import write_site
from tex_parser import parse_sheet

PROJECT = Path(__file__).resolve().parent.parent
# V2 keeps no .tex files: it reads them (read-only) from the original app next to it.
LATEX = PROJECT.parent / "formula-app" / "latex"

# Colour used for sections that have no \sect{colour}{...}, one per sheet.
SHEET_COLORS = ["#1F6FB2", "#2E8B57", "#8E44AD", "#C0392B", "#D35400", "#16A085"]


def find_sheets(latex_dir: Path) -> list[tuple[str, list[Path]]]:
    """Return [(sheet_name, [tex files])] for everything in latex_dir."""
    found = []
    for folder in sorted(p for p in latex_dir.iterdir() if p.is_dir()):
        tex_files = sorted(folder.rglob("*.tex"))
        if tex_files:
            found.append((folder.name, tex_files))
    for tex in sorted(latex_dir.glob("*.tex")):
        found.append((tex.stem, [tex]))
    return found


def pretty_name(folder_name: str) -> str:
    """'fluid_mechanics' -> 'Fluid Mechanics'"""
    return folder_name.replace("_", " ").replace("-", " ").title()


def build(latex_dir: Path, out_dir: Path) -> bool:
    sheets_found = find_sheets(latex_dir)
    if not sheets_found:
        print(f"No .tex files found in {latex_dir}")
        return False

    sheets, sources = [], []
    for i, (name, tex_files) in enumerate(sheets_found):
        unknown: set[str] = set()
        sheet = parse_sheet(name.lower(), pretty_name(name), tex_files,
                            SHEET_COLORS[i % len(SHEET_COLORS)], unknown)
        sheets.append(sheet)
        sources += [str(p.relative_to(latex_dir)).replace("\\", "/") for p in tex_files]

        print(f"  {sheet.name:<14} {len(sheet.sections):>3} sections  {sheet.card_count():>4} cards")
        if unknown:
            print(f"    note: these LaTeX commands were left out: \\{', \\'.join(sorted(unknown))}")
            print("          add them to latex_utils.py if they should show up.")

    for path in write_site(sheets, sources, out_dir):
        print(f"  wrote {path.relative_to(PROJECT)}")
    return True


def serve(out_dir: Path, lan: bool, port: int = 8000) -> None:
    host = "0.0.0.0" if lan else "127.0.0.1"
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(out_dir))
    server = http.server.ThreadingHTTPServer((host, port), handler)
    url = f"http://localhost:{port}/"
    print(f"\nServing on {url}  (press Ctrl+C to stop)")
    if lan:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))           # finds this computer's Wi-Fi address
            print(f"On your phone (same Wi-Fi): http://{s.getsockname()[0]}:{port}/")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


def run(*command: str) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=PROJECT, text=True, capture_output=True)


def publish(message: str) -> bool:
    """Run the tests, then commit everything and push it to GitHub."""
    print("\nRunning tests...")
    tests = run(sys.executable, "-m", "unittest", "discover", "-s", "tests")
    if tests.returncode != 0:
        print(tests.stderr)
        print("Tests failed, so nothing was published. Fix the problem above first.")
        return False

    run("git", "add", "-A")
    if run("git", "diff", "--cached", "--quiet").returncode == 0:
        print("Nothing changed since the last publish.")
        return True
    commit = run("git", "commit", "-m", message)
    print(commit.stdout.strip() or commit.stderr.strip())
    push = run("git", "push")
    if push.returncode != 0:
        print(push.stderr)
        print("Push failed. Check your internet connection and GitHub login.")
        return False
    print("Pushed. GitHub is publishing the new version (about 1 minute);")
    print("see the Actions tab of your repository for progress.")
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build the Formula Finder app from LaTeX.")
    parser.add_argument("--latex", type=Path, default=LATEX, help="folder with your .tex files")
    parser.add_argument("--out", type=Path, default=PROJECT / "web", help="where to write the app")
    parser.add_argument("--serve", action="store_true", help="open the app in your browser afterwards")
    parser.add_argument("--lan", action="store_true", help="with --serve: allow phones on your Wi-Fi")
    parser.add_argument("--publish", action="store_true", help="test, build, commit and push to GitHub")
    parser.add_argument("-m", "--message", default="Update formulas", help="commit message for --publish")
    args = parser.parse_args(argv)
    args.latex, args.out = args.latex.resolve(), args.out.resolve()

    print(f"Reading {args.latex}")
    if not build(args.latex, args.out):
        return 1
    if args.publish and not publish(args.message):
        return 1
    if args.serve:
        serve(args.out, args.lan)
    return 0


if __name__ == "__main__":
    sys.exit(main())
