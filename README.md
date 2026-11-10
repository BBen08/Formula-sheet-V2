# Formula Finder V2 (test copy)

A test copy of Formula Finder with a login, kept fully separate from the
original app in `../formula-app` (own folder, own git repo, own saved
settings and offline storage). V2 has no .tex files of its own: it reads
them, read-only, from `../formula-app/latex`. The original app is never
changed by anything in this folder.


A searchable formula sheet built from your own LaTeX files. You type part of a
formula's name ("parts", "buoyancy", "de moivre") and you get the formula,
drawn properly, with your explanations. It runs in any browser, so it works on
your computer, iPad and iPhone.

It only uses Python's standard library, so there is nothing to install apart from Python itself.

---

## 1. Run it

Open the `formula-app` folder in **Positron** or **VS Code** (File → Open Folder).

**Easiest:** open the *Run and Debug* panel, choose **Build app and open in browser**, then press **F5**.

**From the terminal** (inside the `formula-app` folder):

```bash
python src/main.py --serve
```

You should see something like:

```
Reading ...\formula-app\latex
  Calculus         9 sections    26 cards
  Statics         11 sections    46 cards
  wrote web\index.html
  wrote web\publish.html
  wrote web\sw.js
```

Without `--serve`, it only builds. You can then double-click `web/index.html` to open it.
That works without internet too: MathJax (which draws the maths) is included in the project.

## 2. Update your formulas

1. Edit a chapter file in `latex/math/` or `latex/physics/` (see *How the app is organised* below).
2. Check it on your computer: **Build app and open in browser** (F5).
3. Send it to your phone: choose **Publish to my phone** in *Run and Debug* and press F5, or run

   ```bash
   python src/main.py --publish -m "Add friction formulas"
   ```

   This runs the tests, then commits and pushes to GitHub. GitHub rebuilds the app and
   puts it online (about a minute; follow along in the repository's **Actions** tab).
   The next time you open the app on your phone with internet, a bar says
   *New formulas are available*. Tap **Reload**.

## 3. How the app is organised

```
latex/
├── math/                          → tab "Math"
│   ├── 00_calculus.tex            →   chapter "Calculus" (your course sheet)
│   ├── 01_algebra_complex.tex     →   chapter "Algebra & Complex Numbers"
│   └── ...
└── physics/                       → tab "Physics"
    ├── 00_statics.tex             →   chapter "Statics" (your course sheet)
    ├── 01_constants.tex           →   chapter "Physical Constants"
    └── ...
```

- **Each folder in `latex/` is a tab.** The tab is named after the folder.
- **Each `.tex` file in a folder is a chapter button** under that tab.
  - A file with **one** section is named after that section (`\sect{...}{Algebra \& Complex Numbers}`).
  - A file with **several** sections is named after the file, without the number:
    `00_calculus.tex` → *Calculus*, `07_fluid_mechanics.tex` → *Fluid Mechanics*.
  - The number at the start of the file name sets the **order** of the buttons.
- **Chapters with several sections** (like Calculus and Statics) get *Jump to* buttons
  for their sections when you open them.
- **Search always looks through everything**, whichever tab or chapter you're on.
  Each result shows where it lives, e.g. *Physics · Statics · Friction*.

**Add a chapter:** put a new `.tex` file in `latex/math/` or `latex/physics/`, for example
`latex/physics/07_dynamics.tex` for a new course. **Add a whole new tab:** make a new
folder in `latex/`, for example `latex/chemistry/`.

## 4. How your LaTeX becomes search cards

| You write | The app shows |
|---|---|
| `\section{Friction}` or `\sect{cInt}{2. Integration}` | a section heading (`\definecolor` colours are used) |
| `\sub{Integration by parts}` or `\subsection{...}` | **one card** with everything up to the next sub-heading |
| a short line of text directly above `\[ ... \]` | **one card** named after that line (Statics style) |
| `\expl{...}` | grey italic explanation |
| `\warn{...}` | red warning with "!" |
| `itemize`, `enumerate`, `tabular`, `tabularx` | lists and tables |
| `% comments` | left out |

A section with no sub-headings and no named formulas becomes a single card named after
the section (for example *SI-Units*).

If the build prints `note: these LaTeX commands were left out: \something`, the app
does not know that command yet. Add it to `TEXT_SYMBOLS` or `WRAP_COMMANDS` in
`src/latex_utils.py`.

## 5. What each file does

```
formula-app/
├── latex/                  your .tex files: one folder per tab, one file per chapter
├── src/
│   ├── main.py             run this: finds your .tex files and builds the app
│   ├── tex_parser.py       splits a folder into chapters, sections and cards
│   ├── latex_utils.py      converts LaTeX text (bold, lists, tables) to HTML
│   ├── models.py           what a Sheet, Section and Card are
│   ├── builder.py          puts everything into web/
│   ├── templates/
│   │   ├── page.html       layout of the page
│   │   ├── style.css       colours, fonts, spacing (colour tokens at the top)
│   │   ├── app.js          search, tabs, "copy LaTeX" button, update bar
│   │   └── sw.js           offline support and updates (service worker)
│   └── static/             copied into web/ as-is: manifest, icons, MathJax
├── tests/                  checks that the parser still works
├── assets/logo.webp        the original logo
├── tools/make_icons.ps1    makes the icon sizes from the logo
├── .github/workflows/      tells GitHub how to build and publish the app
└── web/                    the finished app (generated: don't edit, it is overwritten)
```

Each Python file starts with a comment that explains it. A good place to start
reading is `tex_parser.py`.

## 6. Tests

Open the **Testing** panel (flask icon) and click **Run All Tests**, or run:

```bash
python -m unittest discover -s tests -v
```

`tests/test_parser.py` checks your real formula sheets, for example that "Integration by
parts" and "Buoyancy (Archimedes)" each become a card. If you rename a heading on
purpose, update the expected name in the test.

## 7. The app on your iPhone or iPad

**Install it (once):** open your GitHub Pages address in **Safari**, tap Share →
**Add to Home Screen** → Add. You get the Formula Finder icon. It opens full screen like a
normal app.

**Offline:** after you have opened it once with internet, it works without internet.
The app, MathJax, the icons and the fonts are saved on the phone by `sw.js` (the
"service worker").

**Updates:** see step 3 of *Update your formulas* above. Your phone never needs a
reinstall.

**Quick test before publishing:** run **Build app, open on phone (same Wi-Fi)**
(or `python src/main.py --serve --lan`). The terminal prints an address such as
`http://192.168.1.23:8000/` to open in Safari. Windows may ask whether Python may use
the network; allow it for private networks. This test version does not work offline,
because iPhones only allow that for https sites like GitHub Pages.

**Change the icon:** replace `assets/logo.webp` and run
`powershell -ExecutionPolicy Bypass -File tools\make_icons.ps1`.

## 8. Search tips

- Every word you type must appear in the card. Fewer, shorter words find more.
- Titles count most, then the section name, then the formulas and explanations.
  Maths names count too, so `arcsin` and `sum` work.
- Press `/` to jump to the search box and `Esc` to clear it.
- The **TeX** button on each card copies its LaTeX source.
