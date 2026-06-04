# md2pdf

> Convert interlinked Markdown files to a beautiful, GitHub-styled PDF — with Mermaid diagrams, LaTeX math, working internal links, and syntax-highlighted code.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://python.org)
[![Node](https://img.shields.io/badge/Node.js-18%2B-green)](https://nodejs.org)

---

## Features

- **Recursive link following** — starts from `home.md` or `index.md` and follows every relative `.md` link (BFS order), assembling all pages into one PDF
- **Mermaid diagrams** — `flowchart`, `sequenceDiagram`, `classDiagram`, `gitGraph`, and more rendered as crisp PNGs
- **LaTeX math** — `$inline$` and `$$display$$` math rendered server-side via [KaTeX](https://katex.org) (no browser needed)
- **GitHub-style CSS** — Inter/system font stack, syntax-highlighted code blocks (Pygments), tables, task lists, blockquotes
- **Working internal links** — cross-document `[text](other.md#heading)` links become clickable PDF bookmarks
- **Page options** — portrait/landscape, custom margins
- **Wiki-style links** — `[[Page]]` and `[[Page|Label]]` syntax supported

---

## Requirements

| Tool | Minimum version | Notes |
|------|----------------|-------|
| Python | 3.9+ | Add to PATH on Windows |
| Node.js | 18+ | [nodejs.org](https://nodejs.org) |
| npm | 9+ | Bundled with Node.js |

---

## Installation

### Linux / macOS

```bash
git clone https://github.com/your-username/md2pdf.git
cd md2pdf
bash install.sh
```

To verify an existing installation without changing anything:

```bash
bash install.sh --check
```

### Windows

Open **PowerShell** (no admin required) and run:

```powershell
git clone https://github.com/your-username/md2pdf.git
cd md2pdf
.\install.ps1
```

To verify only:

```powershell
.\install.ps1 -Check
```

> **Tip:** If you get a script execution policy error, run:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
> ```

### What the installer does

1. Checks Python 3.9+ and Node.js 18+ are on `PATH`
2. Installs Python packages: `weasyprint`, `markdown`, `pymdown-extensions`, `pygments`
3. Runs `npm install` (pulls `@mermaid-js/mermaid-cli` + Puppeteer)
4. Downloads the Chromium headless shell binary (~113 MB) needed by Mermaid CLI

### Manual installation

```bash
# Python dependencies
pip install -r requirements.txt

# Node dependencies
npm install
```

Then download Chromium headless shell manually:

**Linux/macOS:**
```bash
curl -L "https://storage.googleapis.com/chrome-for-testing-public/148.0.7778.97/linux64/chrome-headless-shell-linux64.zip" \
  -o /tmp/chs.zip
mkdir -p ~/.cache/puppeteer/chrome-headless-shell/linux-148.0.7778.97
cd ~/.cache/puppeteer/chrome-headless-shell/linux-148.0.7778.97
unzip /tmp/chs.zip && chmod +x chrome-headless-shell-linux64/chrome-headless-shell
```

**Windows (PowerShell):**
```powershell
$dest = "$env:USERPROFILE\.cache\puppeteer\chrome-headless-shell\win64-148.0.7778.97"
New-Item -ItemType Directory -Force -Path $dest
Invoke-WebRequest "https://storage.googleapis.com/chrome-for-testing-public/148.0.7778.97/win64/chrome-headless-shell-win64.zip" -OutFile "$dest\chs.zip"
Expand-Archive "$dest\chs.zip" -DestinationPath $dest
```

---

## Usage

```bash
python3 md2pdf.py <input> [output.pdf] [options]
```

| Argument | Description |
|----------|-------------|
| `input` | Directory (auto-finds `home.md`/`index.md`) or a single `.md` file |
| `output` | Output PDF path (default: `<input>/output.pdf`) |
| `-o <p\|l>` | Orientation — `p` portrait *(default)*, `l` landscape |
| `-m T L B R` | Margins in mm — top, left, bottom, right *(default: 20 20 25 20)* |

### Examples

```bash
# Convert a docs directory (auto-detects home.md)
python3 md2pdf.py docs/

# Explicit output path
python3 md2pdf.py docs/ manual.pdf

# Landscape with narrow margins
python3 md2pdf.py docs/ manual.pdf -o l -m 12 10 15 10

# Single file
python3 md2pdf.py README.md output.pdf

# Portrait with wide margins
python3 md2pdf.py wiki/ wiki.pdf -m 25 30 25 30
```

### Shortcut alias

**Linux/macOS** — add to `~/.bashrc` or `~/.zshrc`:
```bash
alias md2pdf='python3 /path/to/md2pdf/md2pdf.py'
```

**Windows** — add to your [PowerShell profile](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_profiles) (`$PROFILE`):
```powershell
function md2pdf { python 'C:\path\to\md2pdf\md2pdf.py' @args }
```

---

## How it works

```
input directory
      │
      ▼
 home.md / index.md          ← entry point
      │
      ▼
 BFS link traversal           ← follows [text](page.md) and [[Page]] links
      │
      ├─ render_math_blocks()  ← KaTeX: $...$ and $$...$$ → HTML spans
      ├─ render_mermaid_blocks() ← mmdc: ```mermaid → PNG images
      ├─ rewrite_image_paths() ← relative imgs → absolute file:// URIs
      ├─ md_to_html_fragment() ← python-markdown + pymdownx extensions
      ├─ prefix_heading_ids()  ← prevents id collisions across documents
      └─ rewrite_internal_links() ← .md hrefs → #anchor-id

      │
      ▼
 build_html()                  ← single HTML document + GitHub CSS + KaTeX CSS
      │
      ▼
 weasyprint → PDF              ← A4/Letter, page numbers, configurable margins
```

---

## Document structure

md2pdf works best with a documentation site structure:

```
docs/
├── home.md          ← or index.md — this is the entry point
├── guide/
│   ├── install.md
│   └── usage.md
├── api/
│   └── reference.md
└── images/
    └── diagram.png
```

Links between pages use standard relative Markdown syntax:

```markdown
See the [Installation Guide](guide/install.md) for setup steps.
Or jump to [API Reference](api/reference.md#methods).
```

---

## Math syntax

Inline math with single `$`:

```markdown
The loss function is $L = \frac{1}{n}\sum_{i=1}^n (y_i - \hat{y}_i)^2$.
```

Display math with double `$$`:

```markdown
$$
\theta_{t+1} = \theta_t - \eta \cdot \frac{\hat{m}_t}{\sqrt{\hat{v}_t} + \epsilon}
$$
```

---

## Mermaid diagrams

````markdown
```mermaid
flowchart TD
    A[Start] --> B{Decision}
    B -- Yes --> C[Do something]
    B -- No  --> D[Do nothing]
```
````

> **Note:** Node labels containing `()` or `||` are automatically quoted by md2pdf before rendering, so diagrams like `node[func()]` work without manual escaping.

---

## Project layout

```
md2pdf/
├── md2pdf.py          # main script (cross-platform)
├── katex_render.js    # Node helper — batch-renders LaTeX → KaTeX HTML
├── install.sh         # installer for Linux / macOS
├── install.ps1        # installer for Windows (PowerShell)
├── requirements.txt   # Python dependencies
├── package.json       # Node dependencies
├── LICENSE            # MIT
└── README.md
```

---

## Troubleshooting

**`mmdc not found`** — run `bash install.sh` to install Node packages.

**`weasyprint` import error** — run `pip install -r requirements.txt`.

**Mermaid diagrams show as code** — the diagram has a syntax error. Check the `[warn] mmdc error` message in the output. Labels with `()` or `||` are auto-fixed; other errors (e.g. unknown node type) need fixing in the source.

**Math shows as raw `$...$`** — ensure `katex_render.js` is present next to `md2pdf.py` and `node` is on your PATH.

**Fonts look wrong in PDF** — weasyprint uses system fonts. Install the `fonts-inter` package (Linux) or any sans-serif system font.

**Windows: `Set-ExecutionPolicy` error** — run `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` then retry.

**Windows: `pip install` fails with permission error** — use `pip install --user -r requirements.txt` or run inside a virtual environment (`python -m venv .venv && .venv\Scripts\activate`).

**Windows: Chrome download fails** — download manually from the URL shown in the installer output and extract to `%USERPROFILE%\.cache\puppeteer\chrome-headless-shell\win64-148.0.7778.97\`.

---

## License

[MIT](LICENSE) © 2026 md2pdf ensismoebius

