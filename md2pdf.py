#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 md2pdf contributors
"""
md2pdf — Markdown → GitHub-styled PDF converter

Recursively follows relative .md links starting from home.md / index.md,
renders Mermaid diagrams and LaTeX math, and produces a single polished PDF.

Usage:
    python3 md2pdf.py <directory|file.md> [output.pdf] [options]

Options:
    -o <p|l>                 Orientation: p=portrait (default), l=landscape
    -m <T> <L> <B> <R>       Margins in mm (default: 20 20 25 20)

Examples:
    python3 md2pdf.py docs/
    python3 md2pdf.py docs/ manual.pdf -o l -m 15 10 20 10
    python3 md2pdf.py README.md output.pdf

See README.md or https://github.com/your-username/md2pdf for full documentation.
"""

import sys
import os
import re
import shutil
import subprocess
import tempfile
import hashlib
import urllib.parse
from pathlib import Path

# ── Locate mmdc ─────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent.resolve()
MMDC_CANDIDATES = [
    SCRIPT_DIR / "node_modules" / ".bin" / "mmdc",
    Path("/usr/local/bin/mmdc"),
    Path("/usr/bin/mmdc"),
    shutil.which("mmdc") and Path(shutil.which("mmdc")),
]
MMDC = next((p for p in MMDC_CANDIDATES if p and p.exists()), None)

# ── Locate KaTeX ─────────────────────────────────────────────────────────────
KATEX_RENDER_JS = SCRIPT_DIR / "katex_render.js"
KATEX_CSS_CANDIDATES = [
    SCRIPT_DIR / "node_modules" / "katex" / "dist" / "katex.min.css",
    SCRIPT_DIR / "node_modules" / "@mermaid-js" / "mermaid-cli" / "node_modules" / "katex" / "dist" / "katex.min.css",
]
KATEX_CSS_PATH = next((p for p in KATEX_CSS_CANDIDATES if p.exists()), None)
KATEX_CSS = KATEX_CSS_PATH.read_text(encoding="utf-8") if KATEX_CSS_PATH else ""
# weasyprint needs font files referenced in CSS to exist; rewrite relative font
# URLs to absolute file:// paths so the CSS is self-contained.
if KATEX_CSS and KATEX_CSS_PATH:
    _css_dir = KATEX_CSS_PATH.parent
    def _fix_font_url(m: re.Match) -> str:
        url = m.group(1).strip("'\"")
        if url.startswith(("http", "data:", "/")):
            return m.group(0)
        abs_font = (_css_dir / url).resolve()
        return f'url("file://{abs_font}")'
    KATEX_CSS = re.sub(r'url\(([^)]+)\)', _fix_font_url, KATEX_CSS)


# ── GitHub-style CSS ─────────────────────────────────────────────────────────
GITHUB_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

* { box-sizing: border-box; }

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Inter", Helvetica, Arial, sans-serif;
    font-size: 16px;
    line-height: 1.6;
    color: #24292f;
    background: #ffffff;
    max-width: 960px;
    margin: 0 auto;
    padding: 32px 40px;
}

h1, h2, h3, h4, h5, h6 {
    margin-top: 24px;
    margin-bottom: 16px;
    font-weight: 600;
    line-height: 1.25;
    color: #1f2328;
}

h1 { font-size: 2em; padding-bottom: 0.3em; border-bottom: 1px solid #d0d7de; }
h2 { font-size: 1.5em; padding-bottom: 0.3em; border-bottom: 1px solid #d0d7de; }
h3 { font-size: 1.25em; }
h4 { font-size: 1em; }
h5 { font-size: 0.875em; }
h6 { font-size: 0.85em; color: #57606a; }

p { margin-top: 0; margin-bottom: 16px; }

a { color: #0969da; text-decoration: none; }
a:hover { text-decoration: underline; }

ul, ol { padding-left: 2em; margin-top: 0; margin-bottom: 16px; }
li { margin-top: 0.25em; }
li > p { margin-top: 16px; }
ul ul, ol ol, ul ol, ol ul { margin-top: 0; margin-bottom: 0; }

blockquote {
    margin: 0 0 16px;
    padding: 0 1em;
    color: #57606a;
    border-left: 0.25em solid #d0d7de;
}
blockquote > :first-child { margin-top: 0; }
blockquote > :last-child { margin-bottom: 0; }

code {
    font-family: ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 85%;
    background: #f6f8fa;
    border-radius: 6px;
    padding: 0.2em 0.4em;
    color: #24292f;
}

pre {
    margin-top: 0;
    margin-bottom: 16px;
    overflow: auto;
    background: #f6f8fa;
    border-radius: 6px;
    padding: 16px;
    line-height: 1.45;
}

pre code {
    display: inline;
    padding: 0;
    margin: 0;
    overflow: visible;
    line-height: inherit;
    background: transparent;
    border: 0;
    font-size: 100%;
}

table {
    border-spacing: 0;
    border-collapse: collapse;
    display: block;
    width: max-content;
    max-width: 100%;
    overflow: auto;
    margin-top: 0;
    margin-bottom: 16px;
}

table th, table td {
    padding: 6px 13px;
    border: 1px solid #d0d7de;
}

table th { font-weight: 600; background: #f6f8fa; }

table tr:nth-child(2n) { background: #f6f8fa; }

img {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 16px auto;
    border-radius: 6px;
}

hr {
    height: 0.25em;
    padding: 0;
    margin: 24px 0;
    background-color: #d0d7de;
    border: 0;
}

.page-break {
    page-break-after: always;
    break-after: page;
    height: 0;
    display: block;
}

.doc-section {
    margin-bottom: 0;
}

/* Syntax highlighting (Pygments github style) */
.highlight .hll { background-color: #ffffcc }
.highlight  { background: #f6f8fa; }
.highlight .c { color: #6e7781; font-style: italic }
.highlight .err { color: #24292f }
.highlight .g { color: #24292f }
.highlight .k { color: #cf222e; font-weight: bold }
.highlight .l { color: #0550ae }
.highlight .n { color: #24292f }
.highlight .o { color: #cf222e }
.highlight .x { color: #24292f }
.highlight .p { color: #24292f }
.highlight .ch { color: #6e7781; font-style: italic }
.highlight .cm { color: #6e7781; font-style: italic }
.highlight .cp { color: #8250df }
.highlight .cpf { color: #6e7781; font-style: italic }
.highlight .c1 { color: #6e7781; font-style: italic }
.highlight .cs { color: #6e7781; font-style: italic }
.highlight .gd { color: #82071e; background-color: #FFEBE9 }
.highlight .ge { color: #24292f; font-style: italic }
.highlight .gr { color: #82071e }
.highlight .gh { color: #0550ae; font-weight: bold }
.highlight .gi { color: #116329; background-color: #DAFBE1 }
.highlight .go { color: #57606a }
.highlight .gp { color: #0550ae; font-weight: bold }
.highlight .gs { color: #24292f; font-weight: bold }
.highlight .gu { color: #0550ae; font-weight: bold }
.highlight .gt { color: #82071e }
.highlight .kc { color: #0550ae; font-weight: bold }
.highlight .kd { color: #cf222e; font-weight: bold }
.highlight .kn { color: #cf222e; font-weight: bold }
.highlight .kp { color: #cf222e; font-weight: bold }
.highlight .kr { color: #cf222e; font-weight: bold }
.highlight .kt { color: #cf222e; font-weight: bold }
.highlight .ld { color: #0550ae }
.highlight .m { color: #0550ae }
.highlight .s { color: #0a3069 }
.highlight .na { color: #116329 }
.highlight .nb { color: #0550ae }
.highlight .nc { color: #953800 }
.highlight .no { color: #0550ae }
.highlight .nd { color: #8250df }
.highlight .ni { color: #24292f }
.highlight .ne { color: #953800 }
.highlight .nf { color: #8250df }
.highlight .nl { color: #116329 }
.highlight .nn { color: #953800 }
.highlight .nx { color: #24292f }
.highlight .py { color: #24292f }
.highlight .nt { color: #116329 }
.highlight .nv { color: #953800 }
.highlight .ow { color: #cf222e; font-weight: bold }
.highlight .w { color: #24292f }
.highlight .mb { color: #0550ae }
.highlight .mf { color: #0550ae }
.highlight .mh { color: #0550ae }
.highlight .mi { color: #0550ae }
.highlight .mo { color: #0550ae }
.highlight .sa { color: #0a3069 }
.highlight .sb { color: #0a3069 }
.highlight .sc { color: #24292f }
.highlight .dl { color: #0a3069 }
.highlight .sd { color: #6e7781; font-style: italic }
.highlight .s2 { color: #0a3069 }
.highlight .se { color: #cf222e }
.highlight .sh { color: #0a3069 }
.highlight .si { color: #24292f }
.highlight .sx { color: #0a3069 }
.highlight .sr { color: #116329 }
.highlight .s1 { color: #0a3069 }
.highlight .ss { color: #0a3069 }
.highlight .bp { color: #0550ae }
.highlight .fm { color: #8250df }
.highlight .vc { color: #953800 }
.highlight .vg { color: #953800 }
.highlight .vi { color: #953800 }
.highlight .vm { color: #953800 }
.highlight .il { color: #0550ae }
"""


# ── Math rendering via KaTeX node helper ────────────────────────────────────

def render_math_blocks(content: str) -> str:
    """
    Replace all LaTeX math in markdown with pre-rendered KaTeX HTML.
    Handles:
      $$...$$  (display, possibly multiline)
      $...$    (inline, single line only, not inside code)
    Protects fenced code blocks from math substitution.
    """
    if not KATEX_RENDER_JS.exists():
        return content

    # ── 1. Extract and protect fenced code blocks ──────────────────────────
    code_blocks: list[str] = []
    def stash_code(m: re.Match) -> str:
        code_blocks.append(m.group(0))
        return f"\x00CODE{len(code_blocks) - 1}\x00"

    # Fenced blocks (``` or ~~~) and indented code blocks
    protected = re.sub(r'(?:```|~~~)[\s\S]*?(?:```|~~~)', stash_code, content)
    protected = re.sub(r'(?m)^(?: {4}|\t).+', stash_code, protected)
    # Inline code `...`
    protected = re.sub(r'`[^`\n]+`', stash_code, protected)

    # ── 2. Collect all math expressions ────────────────────────────────────
    math_items: list[dict] = []   # [{"math": str, "display": bool}]
    placeholders: list[str] = []

    def stash_display(m: re.Match) -> str:
        src = m.group(1).strip()
        idx = len(math_items)
        math_items.append({"math": src, "display": True})
        ph = f"\x01MATH{idx}\x01"
        placeholders.append(ph)
        return ph

    def stash_inline(m: re.Match) -> str:
        src = m.group(1).strip()
        if not src:
            return m.group(0)
        idx = len(math_items)
        math_items.append({"math": src, "display": False})
        ph = f"\x01MATH{idx}\x01"
        placeholders.append(ph)
        return ph

    # Display math: $$...$$  (multiline)
    protected = re.sub(r'\$\$([\s\S]+?)\$\$', stash_display, protected)
    # Inline math: $...$ (not empty, not starting with space)
    protected = re.sub(r'(?<!\\)\$(?!\s)([^$\n]+?)(?<!\s)\$', stash_inline, protected)

    if not math_items:
        # Restore code blocks and return
        result = protected
        for i, blk in enumerate(code_blocks):
            result = result.replace(f"\x00CODE{i}\x00", blk)
        return result

    # ── 3. Batch-render via Node/KaTeX ─────────────────────────────────────
    import json
    stdin_data = "\n".join(json.dumps(item) for item in math_items)
    try:
        proc = subprocess.run(
            ["node", str(KATEX_RENDER_JS)],
            input=stdin_data, capture_output=True, text=True, timeout=30,
        )
        rendered_lines = proc.stdout.splitlines()
    except Exception as e:
        print(f"  [warn] KaTeX render failed: {e}", file=sys.stderr)
        rendered_lines = []

    # ── 4. Substitute placeholders with rendered HTML ───────────────────────
    result = protected
    for idx, item in enumerate(math_items):
        ph = f"\x01MATH{idx}\x01"
        if idx < len(rendered_lines) and rendered_lines[idx]:
            rendered = rendered_lines[idx]
            # Wrap display math in a block div
            if item["display"]:
                rendered = f'<div class="math-display">{rendered}</div>'
        else:
            # Fallback: show LaTeX source in a code span
            escaped = item["math"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            rendered = f'<code class="math-fallback">{escaped}</code>'
        result = result.replace(ph, rendered)

    # ── 5. Restore code blocks ──────────────────────────────────────────────
    for i, blk in enumerate(code_blocks):
        result = result.replace(f"\x00CODE{i}\x00", blk)

    return result


# ── Markdown extensions ───────────────────────────────────────────────────────
MD_EXTENSIONS = [
    "extra",          # tables, footnotes, attr_list, def_list, abbr, fenced_code
    "codehilite",     # syntax highlighting via pygments
    "toc",            # [TOC] support
    "meta",           # YAML front-matter
    "sane_lists",     # better list parsing
    "nl2br",          # newline → <br>
    "pymdownx.superfences",   # nested fences, mermaid support
    "pymdownx.tasklist",      # - [x] checkboxes
    "pymdownx.highlight",     # improved highlighting
    "pymdownx.inlinehilite",  # inline code highlighting
    "pymdownx.emoji",         # :emoji: support (no-op if no index)
    "pymdownx.smartsymbols",  # → ® © etc.
]

MD_EXTENSION_CONFIGS = {
    "codehilite": {
        "guess_lang": False,
        "css_class": "highlight",
    },
    "pymdownx.highlight": {
        "css_class": "highlight",
        "guess_lang": False,
    },
    "toc": {
        "permalink": True,
    },
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def normalize_path(base_dir: Path, href: str) -> Path | None:
    """Resolve a relative markdown link to an absolute path."""
    if href.startswith(("http://", "https://", "ftp://", "mailto:", "#")):
        return None
    # Strip anchors
    href = href.split("#")[0]
    if not href:
        return None
    decoded = urllib.parse.unquote(href)
    candidate = (base_dir / decoded).resolve()
    if candidate.suffix.lower() in (".md", ".markdown", ""):
        # Try as-is, then with .md
        if candidate.exists():
            return candidate
        for ext in [".md", ".markdown"]:
            with_ext = candidate.with_suffix(ext)
            if with_ext.exists():
                return with_ext
    return None


def find_md_links(content: str) -> list[str]:
    """Extract all relative markdown link targets from content."""
    # [text](href), ![alt](href), and wiki-style [[Page]]
    links: list[str] = []
    # Standard markdown links
    for m in re.finditer(r'\[(?:[^\]]*)\]\(([^)]+)\)', content):
        href = m.group(1).strip()
        links.append(href)
    # Wiki-style [[Page]] or [[Page|Label]]
    for m in re.finditer(r'\[\[([^\]|]+)(?:\|[^\]]*)?\]\]', content):
        href = m.group(1).strip()
        if not href.lower().endswith((".md", ".markdown")):
            href += ".md"
        links.append(href)
    return links


def sanitize_mermaid(src: str) -> str:
    """
    Quote mermaid flowchart node labels that contain characters the parser
    mis-identifies as shape tokens:
      ()   → parsed as stadium/subroutine shape start
      ||   → parsed as pipe separator
      ²³   → non-ASCII in some contexts

    Strategy: for every `id[label]` where label is unquoted and contains
    those chars, rewrite to `id["label"]`.  Skips already-quoted labels.
    Also handles `id([label])` and `id{label}` shapes.
    """
    # Characters that trip up the mermaid parser inside labels
    NEEDS_QUOTE = re.compile(r'[()]|\|\|')

    def quote_bracket_label(m: re.Match) -> str:
        node_id  = m.group(1)   # e.g. "collate" or "I"
        label    = m.group(2)   # content inside [...]
        # Already quoted — leave alone
        if label.startswith(('"', "'")):
            return m.group(0)
        if NEEDS_QUOTE.search(label):
            # Escape any embedded double-quotes, then wrap
            safe = label.replace('"', '#quot;')
            return f'{node_id}["{safe}"]'
        return m.group(0)

    # Match  word[unquoted label]  (square-bracket rectangle nodes only)
    # Non-greedy, won't cross line boundaries unintentionally
    src = re.sub(r'(\w+)\[([^\]\n]+)\]', quote_bracket_label, src)
    return src


def render_mermaid_blocks(content: str, base_dir: Path, tmp_dir: Path) -> str:
    """Replace ```mermaid ... ``` blocks with <img> tags (rendered PNG)."""
    if MMDC is None:
        print("  [warn] mmdc not found — mermaid blocks left as code", file=sys.stderr)
        return content

    def replace_block(m: re.Match) -> str:
        diagram_src = sanitize_mermaid(m.group(1))
        # Hash after sanitization so cache is keyed on the fixed source
        digest = hashlib.md5(diagram_src.encode()).hexdigest()[:12]
        png_path = tmp_dir / f"mermaid_{digest}.png"

        if not png_path.exists():
            mmd_path = tmp_dir / f"mermaid_{digest}.mmd"
            mmd_path.write_text(diagram_src, encoding="utf-8")
            try:
                result = subprocess.run(
                    [str(MMDC), "-i", str(mmd_path), "-o", str(png_path),
                     "-b", "white", "--scale", "2"],
                    capture_output=True, text=True, timeout=60,
                )
                if result.returncode != 0:
                    print(f"  [warn] mmdc error: {result.stderr.strip()}", file=sys.stderr)
                    return m.group(0)  # Keep original on failure
            except subprocess.TimeoutExpired:
                print("  [warn] mmdc timed out", file=sys.stderr)
                return m.group(0)

        return f'\n<img src="{png_path}" alt="Mermaid diagram" style="max-width:100%;"/>\n'

    # Match ```mermaid ... ``` (case-insensitive, multiline)
    pattern = re.compile(r'```mermaid\s*\n(.*?)```', re.DOTALL | re.IGNORECASE)
    return pattern.sub(replace_block, content)


def rewrite_image_paths(content: str, base_dir: Path) -> str:
    """Rewrite relative image paths to absolute file:// URIs for weasyprint."""
    def replace_img(m: re.Match) -> str:
        alt = m.group(1)
        src = m.group(2).strip()
        if src.startswith(("http://", "https://", "data:", "file://")):
            return m.group(0)
        decoded = urllib.parse.unquote(src)
        abs_path = (base_dir / decoded).resolve()
        if abs_path.exists():
            return f"![{alt}](file://{abs_path})"
        return m.group(0)

    return re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', replace_img, content)


def path_to_anchor(doc_path: Path, root: Path) -> str:
    """Stable, unique anchor id for a document, derived from its relative path."""
    try:
        rel = doc_path.relative_to(root)
    except ValueError:
        rel = Path(doc_path.name)
    slug = str(rel).lower()
    slug = re.sub(r'[\./ \\]+', '-', slug)   # separators → dash
    slug = re.sub(r'[^a-z0-9\-]', '', slug)   # strip non-alphanum
    slug = slug.strip('-')
    return f"doc-{slug}"


def prefix_heading_ids(html: str, prefix: str) -> str:
    """Prefix every id="..." on heading elements to avoid cross-doc collisions."""
    # id= on <h1>–<h6> and on <a> (permalink anchors generated by toc extension)
    return re.sub(
        r'(<(?:h[1-6]|a)\b[^>]*?)\bid=(["\'])([^"\'>]+)\2',
        lambda m: f'{m.group(1)}id={m.group(2)}{prefix}--{m.group(3)}{m.group(2)}',
        html,
    )


def rewrite_internal_links(html: str, doc_path: Path, root: Path,
                           anchor_map: dict[Path, str]) -> str:
    """Rewrite <a href="..."> that target .md files to #anchor-id."""
    def replace_href(m: re.Match) -> str:
        before = m.group(1)   # attributes before href value
        quote  = m.group(2)
        href   = m.group(3)
        after  = m.group(4)   # rest of tag

        if href.startswith(("http://", "https://", "ftp://", "mailto:", "data:", "file://")):
            return m.group(0)

        # Split off in-page fragment
        if '#' in href:
            file_part, fragment = href.split('#', 1)
        else:
            file_part, fragment = href, ''

        # Pure in-page anchors (#heading) — leave file_part empty
        if not file_part:
            return m.group(0)

        # Resolve the target file
        decoded = urllib.parse.unquote(file_part)
        candidate = (doc_path.parent / decoded).resolve()
        # Try with .md extension if needed
        target = None
        if candidate in anchor_map:
            target = candidate
        else:
            for ext in ('.md', '.markdown'):
                with_ext = candidate.with_suffix(ext)
                if with_ext in anchor_map:
                    target = with_ext
                    break

        if target is None:
            return m.group(0)  # Not a known doc — leave unchanged

        section_anchor = anchor_map[target]
        if fragment:
            # Point to prefixed heading inside that section
            frag_slug = fragment.lower()
            new_href = f"#{section_anchor}--{frag_slug}"
        else:
            new_href = f"#{section_anchor}"

        return f'<a {before}href={quote}{new_href}{quote}{after}>'

    # Match <a ...href="..."...>
    pattern = re.compile(
        r'<a\s+([^>]*?)href=(["\'])([^"\'>]+)\2([^>]*)>',
        re.IGNORECASE,
    )
    return pattern.sub(replace_href, html)


def collect_docs(start_file: Path) -> list[Path]:
    """
    BFS traversal following relative .md links from start_file.
    Returns ordered list of unique .md files.
    """
    visited: list[Path] = []
    seen: set[Path] = set()
    queue: list[Path] = [start_file.resolve()]

    while queue:
        current = queue.pop(0)
        current = current.resolve()
        if current in seen:
            continue
        if not current.exists():
            print(f"  [warn] linked file not found: {current}", file=sys.stderr)
            continue
        seen.add(current)
        visited.append(current)

        content = current.read_text(encoding="utf-8", errors="replace")
        links = find_md_links(content)
        base = current.parent
        for href in links:
            resolved = normalize_path(base, href)
            if resolved and resolved not in seen:
                queue.append(resolved)

    return visited


def md_to_html_fragment(content: str) -> str:
    """Convert markdown string to HTML fragment."""
    import markdown as md_lib
    extensions = []
    for ext in MD_EXTENSIONS:
        try:
            extensions.append(ext)
        except Exception:
            pass

    converter = md_lib.Markdown(
        extensions=extensions,
        extension_configs=MD_EXTENSION_CONFIGS,
        output_format="html",
    )
    try:
        return converter.convert(content)
    except Exception as e:
        # Fallback: try with fewer extensions
        print(f"  [warn] markdown extension error ({e}), retrying with basic extensions", file=sys.stderr)
        fallback_exts = ["extra", "codehilite", "toc", "sane_lists", "nl2br"]
        converter = md_lib.Markdown(
            extensions=fallback_exts,
            extension_configs={"codehilite": {"guess_lang": False, "css_class": "highlight"}},
            output_format="html",
        )
        return converter.convert(content)


def build_html(sections: list[tuple[str, str, str]]) -> str:
    """
    Build a complete HTML document from (title, anchor_id, html_fragment) triples.
    """
    katex_style = f"<style>{KATEX_CSS}</style>" if KATEX_CSS else ""
    extra_css = """
<style>
.math-display { display: block; text-align: center; margin: 1em 0; overflow-x: auto; }
.katex-display { overflow-x: auto; overflow-y: hidden; }
.math-fallback { background: #fff3cd; padding: 2px 4px; border-radius: 3px; font-style: italic; }
</style>"""
    parts = ["<!DOCTYPE html>", "<html lang='en'>", "<head>",
             "<meta charset='UTF-8'>",
             "<meta name='viewport' content='width=device-width, initial-scale=1'>",
             f"<style>{GITHUB_CSS}</style>",
             katex_style,
             extra_css,
             "</head>", "<body>"]

    for i, (title, anchor_id, fragment) in enumerate(sections):
        parts.append(f"<div id='{anchor_id}' class='doc-section'>")
        if i > 0:
            parts.append(f"<hr class='section-sep' style='margin: 2em 0; border-color: #d0d7de;'>")
            parts.append(f"<p style='color:#57606a;font-size:0.8em;margin-bottom:1em;'>"
                         f"&#128196; {title}</p>")
        parts.append(fragment)
        parts.append("</div>")
        if i < len(sections) - 1:
            parts.append("<div class='page-break'></div>")

    parts += ["</body>", "</html>"]
    return "\n".join(parts)


def convert(input_path: Path, output_pdf: Path,
            orientation: str = 'portrait',
            margins: tuple[str, str, str, str] = ('20mm', '20mm', '25mm', '20mm')) -> None:
    """Main conversion pipeline."""
    # Resolve start file
    if input_path.is_dir():
        candidates = ["home.md", "Home.md", "HOME.md", "index.md", "Index.md", "INDEX.md",
                      "readme.md", "README.md"]
        start = None
        for name in candidates:
            p = input_path / name
            if p.exists():
                start = p
                break
        if start is None:
            # Pick first .md file found
            md_files = sorted(input_path.rglob("*.md"))
            if not md_files:
                print(f"Error: no .md files found in {input_path}", file=sys.stderr)
                sys.exit(1)
            start = md_files[0]
            print(f"  [info] no home/index found, starting from: {start.name}")
        else:
            print(f"  [info] start page: {start.name}")
    else:
        start = input_path
        print(f"  [info] single file mode: {start.name}")

    print(f"  [info] collecting linked documents...")
    docs = collect_docs(start)
    print(f"  [info] found {len(docs)} document(s):")
    for d in docs:
        print(f"         - {d}")

    # Root for relative anchor slugs = parent of start file / given dir
    anchor_root = input_path if input_path.is_dir() else input_path.parent
    # Build path → anchor-id map for all collected docs
    anchor_map: dict[Path, str] = {
        doc.resolve(): path_to_anchor(doc.resolve(), anchor_root.resolve())
        for doc in docs
    }

    with tempfile.TemporaryDirectory(prefix="md2pdf_") as tmp_str:
        tmp_dir = Path(tmp_str)
        sections: list[tuple[str, str, str]] = []

        for doc in docs:
            print(f"  [proc] {doc.name}")
            content = doc.read_text(encoding="utf-8", errors="replace")
            # Strip YAML front matter
            content = re.sub(r'^---\s*\n.*?\n---\s*\n', '', content, count=1, flags=re.DOTALL)
            # Render math (KaTeX) — must be before markdown conversion
            content = render_math_blocks(content)
            # Render mermaid blocks
            content = render_mermaid_blocks(content, doc.parent, tmp_dir)
            # Rewrite relative image paths to absolute
            content = rewrite_image_paths(content, doc.parent)
            # Convert to HTML
            html_frag = md_to_html_fragment(content)
            anchor_id = anchor_map[doc.resolve()]
            # Prefix heading ids to avoid cross-doc collisions
            html_frag = prefix_heading_ids(html_frag, anchor_id)
            # Rewrite .md hrefs to internal #anchor links
            html_frag = rewrite_internal_links(html_frag, doc.resolve(), anchor_root.resolve(), anchor_map)
            sections.append((doc.name, anchor_id, html_frag))

        print(f"  [info] building HTML...")
        full_html = build_html(sections)

        html_path = tmp_dir / "document.html"
        html_path.write_text(full_html, encoding="utf-8")

        print(f"  [info] rendering PDF with weasyprint...")
        try:
            from weasyprint import HTML, CSS
            from weasyprint.text.fonts import FontConfiguration
            font_config = FontConfiguration()

            # Page margins and print settings
            size_decl = f"A4 {orientation}"
            top, left, bottom, right = margins
            print_css = CSS(string=f"""
                @page {{
                    size: {size_decl};
                    margin: {top} {right} {bottom} {left};
                    @bottom-center {{
                        content: counter(page) " / " counter(pages);
                        font-size: 10px;
                        color: #57606a;
                    }}
                }}
                body {{ max-width: none; padding: 0; }}
            """, font_config=font_config)

            HTML(filename=str(html_path)).write_pdf(
                target=str(output_pdf),
                stylesheets=[print_css],
                font_config=font_config,
                presentational_hints=True,
            )
        except Exception as e:
            print(f"Error during PDF generation: {e}", file=sys.stderr)
            sys.exit(1)

        print(f"\n  [done] PDF written to: {output_pdf}")
        size_mb = output_pdf.stat().st_size / (1024 * 1024)
        print(f"         Size: {size_mb:.2f} MB")


# ── Entry point ───────────────────────────────────────────────────────────────

def _parse_margin(value: str) -> str:
    """Append 'mm' if the value is a bare number."""
    return value if re.search(r'[a-zA-Z%]', value) else value + 'mm'


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        prog='md2pdf',
        description='Convert linked Markdown files to a GitHub-styled PDF.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            'examples:\n'
            '  md2pdf.py docs/            # auto-finds home.md / index.md\n'
            '  md2pdf.py docs/ out.pdf\n'
            '  md2pdf.py README.md out.pdf -o l -m 15 10 20 10\n'
        ),
    )
    parser.add_argument('input',  help='Directory or .md file to convert')
    parser.add_argument('output', nargs='?', help='Output PDF path (default: <input>/output.pdf)')
    parser.add_argument(
        '-o', '--orientation',
        choices=['p', 'l', 'portrait', 'landscape'],
        default='p',
        metavar='<p|l>',
        help='Page orientation: p=portrait (default), l=landscape',
    )
    parser.add_argument(
        '-m', '--margins',
        nargs=4,
        metavar=('TOP', 'LEFT', 'BOTTOM', 'RIGHT'),
        default=['20', '20', '25', '20'],
        help='Page margins in mm (default: 20 20 25 20)',
    )

    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    if not input_path.exists():
        parser.error(f"'{input_path}' does not exist")

    if args.output:
        output_pdf = Path(args.output).resolve()
    else:
        base = input_path if input_path.is_dir() else input_path.parent
        output_pdf = base / 'output.pdf'

    orientation = 'landscape' if args.orientation in ('l', 'landscape') else 'portrait'
    margins = tuple(_parse_margin(v) for v in args.margins)  # (top, left, bottom, right)

    print('md2pdf — Markdown → GitHub-style PDF')
    print(f'  input      : {input_path}')
    print(f'  output     : {output_pdf}')
    print(f'  orientation: {orientation}')
    print(f'  margins    : top={margins[0]} left={margins[1]} bottom={margins[2]} right={margins[3]}')
    print()

    convert(input_path, output_pdf, orientation=orientation, margins=margins)


if __name__ == '__main__':
    main()
