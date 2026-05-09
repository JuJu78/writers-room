#!/usr/bin/env python3
"""Writers Room — Markdown → standalone HTML renderer.

Produces a single self-contained HTML file from a Markdown article. CSS is
embedded in <style>; no external dependencies, no network calls.

Two CSS sources are supported:

    --css custom.css   → inline that file verbatim
    (default)          → use the editorial-neutral default CSS shipped here

The Design Extraction agent (see SKILL.md) writes its derived CSS to a file
that the Coordinator passes via --css.

Markdown-to-HTML conversion uses the `markdown` package if installed (better
table/footnote support); otherwise a minimal built-in converter handles the
constructs an Writers Room article uses.

Usage
-----
    python render_html.py article.md --output article.html
    python render_html.py article.md --output article.html --config config.yml
    python render_html.py article.md --output article.html --css design.css \
        --title "My title" --meta "My meta description" --open

Exit code 0 on success.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Default CSS — editorial neutral
# ---------------------------------------------------------------------------

DEFAULT_CSS = """
:root {
  --bg: #ffffff;
  --fg: #1a1a1a;
  --muted: #6b7280;
  --accent: #2563eb;
  --accent-soft: #dbeafe;
  --code-bg: #f3f4f6;
  --code-fg: #1f2937;
  --rule: #e5e7eb;
  --callout-note: #2563eb;
  --callout-tip: #16a34a;
  --callout-warn: #d97706;
  --callout-danger: #dc2626;
  --max-width: 680px;
  --font-body: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --font-mono: ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0d0d0f;
    --fg: #e5e7eb;
    --muted: #9ca3af;
    --accent: #60a5fa;
    --accent-soft: #1e3a8a;
    --code-bg: #1c1d20;
    --code-fg: #e5e7eb;
    --rule: #2a2b30;
  }
}

* { box-sizing: border-box; }

html { scroll-behavior: smooth; }

body {
  margin: 0;
  background: var(--bg);
  color: var(--fg);
  font-family: var(--font-body);
  font-size: 18px;
  line-height: 1.65;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-rendering: optimizeLegibility;
}

main {
  max-width: var(--max-width);
  margin: 0 auto;
  padding: 4rem 1.5rem 6rem;
}

.article-meta {
  color: var(--muted);
  font-size: 0.95rem;
  margin: 0 0 2.5rem;
}

.preview-meta {
  margin: 0 0 3rem;
  padding: 1rem 1.25rem;
  border: 1px dashed var(--rule);
  border-radius: 6px;
  font-size: 0.92rem;
  color: var(--fg);
  font-family: var(--font-mono);
  line-height: 1.5;
}

.preview-meta__row {
  display: flex;
  gap: 0.75rem;
  align-items: baseline;
}

.preview-meta__row + .preview-meta__row {
  margin-top: 0.5rem;
}

.preview-meta__label {
  font-weight: 700;
  color: var(--accent);
  flex-shrink: 0;
  min-width: 9rem;
  text-transform: none;
}

.preview-meta__value {
  word-break: break-word;
  color: var(--fg);
}

h1 {
  font-size: 2.25rem;
  line-height: 1.15;
  letter-spacing: -0.02em;
  margin: 0 0 0.5rem;
  font-weight: 700;
}

h2 {
  font-size: 1.5rem;
  line-height: 1.25;
  letter-spacing: -0.01em;
  margin: 3rem 0 0.75rem;
  font-weight: 700;
}

h3 {
  font-size: 1.2rem;
  line-height: 1.3;
  margin: 2rem 0 0.5rem;
  font-weight: 700;
}

h4, h5, h6 {
  margin: 1.5rem 0 0.5rem;
  font-weight: 700;
}

p { margin: 0 0 1.25rem; }

a {
  color: var(--accent);
  text-decoration: underline;
  text-underline-offset: 0.2em;
  text-decoration-thickness: 1px;
  transition: text-decoration-thickness 0.15s ease;
}

a:hover { text-decoration-thickness: 2px; }

ul, ol { padding-left: 1.4rem; margin: 0 0 1.25rem; }
li { margin: 0.4rem 0; }
li > p { margin: 0; }

blockquote {
  margin: 1.5rem 0;
  padding: 0.5rem 1.25rem;
  border-left: 3px solid var(--accent);
  color: var(--muted);
  font-style: italic;
}

blockquote p:last-child { margin-bottom: 0; }

code {
  font-family: var(--font-mono);
  font-size: 0.92em;
  padding: 0.15em 0.35em;
  background: var(--code-bg);
  color: var(--code-fg);
  border-radius: 4px;
}

pre {
  background: var(--code-bg);
  color: var(--code-fg);
  padding: 1rem 1.25rem;
  border-radius: 6px;
  overflow-x: auto;
  margin: 1.5rem 0;
  font-size: 0.92em;
  line-height: 1.55;
}

pre code {
  padding: 0;
  background: none;
  border-radius: 0;
  font-size: 1em;
}

hr {
  border: 0;
  border-top: 1px solid var(--rule);
  margin: 2.5rem 0;
}

table {
  border-collapse: collapse;
  width: 100%;
  margin: 1.5rem 0;
  font-size: 0.95em;
}

th, td {
  padding: 0.6rem 0.8rem;
  border-bottom: 1px solid var(--rule);
  text-align: left;
}

th {
  font-weight: 700;
  color: var(--fg);
  border-bottom: 2px solid var(--rule);
}

img {
  max-width: 100%;
  height: auto;
  border-radius: 6px;
  margin: 1.5rem 0;
}

figure { margin: 1.5rem 0; }

figcaption {
  font-size: 0.9em;
  color: var(--muted);
  text-align: center;
  margin-top: 0.5rem;
}

/* GitHub-style alerts */
.callout {
  margin: 1.5rem 0;
  padding: 0.85rem 1.25rem;
  border-left: 4px solid var(--callout-note);
  background: color-mix(in srgb, var(--accent-soft) 40%, transparent);
  border-radius: 0 4px 4px 0;
}
.callout--note { border-left-color: var(--callout-note); }
.callout--tip { border-left-color: var(--callout-tip); }
.callout--warning { border-left-color: var(--callout-warn); }
.callout--danger { border-left-color: var(--callout-danger); }
.callout__label {
  font-weight: 700;
  font-size: 0.85em;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.35rem;
}
.callout--note .callout__label { color: var(--callout-note); }
.callout--tip .callout__label { color: var(--callout-tip); }
.callout--warning .callout__label { color: var(--callout-warn); }
.callout--danger .callout__label { color: var(--callout-danger); }
.callout p:last-child { margin-bottom: 0; }

@media (max-width: 720px) {
  main { padding: 2rem 1.25rem 3rem; }
  h1 { font-size: 1.85rem; }
  h2 { font-size: 1.3rem; }
  body { font-size: 17px; }
}

@media print {
  body { background: white; color: black; }
  main { max-width: none; padding: 0; }
  a { color: black; text-decoration: underline; }
  pre, code { background: #f4f4f4; }
}
""".strip()


# ---------------------------------------------------------------------------
# Built-in minimal markdown → HTML converter
# ---------------------------------------------------------------------------

CALLOUT_TYPES = {"NOTE": "note", "TIP": "tip", "IMPORTANT": "note", "WARNING": "warning", "CAUTION": "danger"}

# Block-level HTML tags whose paragraphs are passed through verbatim, not wrapped in <p>.
# Roughly CommonMark "HTML block" rule type 6, plus svg/figure/canvas which are common in articles.
HTML_BLOCK_TAGS = (
    "svg", "figure", "div", "table", "aside", "details", "section", "nav",
    "video", "audio", "iframe", "script", "style", "pre", "blockquote",
    "address", "article", "footer", "header", "main", "form", "canvas", "picture",
    "hr", "p", "h1", "h2", "h3", "h4", "h5", "h6",
)
HTML_BLOCK_OPEN_RE = re.compile(
    r"^<(" + "|".join(HTML_BLOCK_TAGS) + r")\b", re.IGNORECASE
)


def _escape(text: str) -> str:
    return html.escape(text, quote=False)


def _inline(text: str) -> str:
    """Apply inline markdown: code, bold, italic, links, images.

    Order matters: code first (its content is escaped and frozen), then images,
    links, bold, italic. Plain text outside spans is HTML-escaped.
    """
    placeholders: list[str] = []

    def stash(html_str: str) -> str:
        placeholders.append(html_str)
        return f"\x00{len(placeholders) - 1}\x00"

    # Inline code: `...`
    text = re.sub(r"`([^`]+)`", lambda m: stash(f"<code>{_escape(m.group(1))}</code>"), text)

    # Images: ![alt](src)
    text = re.sub(
        r"!\[([^\]]*)\]\(([^)]+)\)",
        lambda m: stash(f'<img src="{_escape(m.group(2).strip())}" alt="{_escape(m.group(1))}">'),
        text,
    )

    # Links: [text](url)
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: stash(f'<a href="{_escape(m.group(2).strip())}">{_escape(m.group(1))}</a>'),
        text,
    )

    # Bold: **text** or __text__
    text = re.sub(r"\*\*([^*]+)\*\*", lambda m: stash(f"<strong>{_escape(m.group(1))}</strong>"), text)
    text = re.sub(r"__([^_]+)__", lambda m: stash(f"<strong>{_escape(m.group(1))}</strong>"), text)

    # Italic: *text* or _text_ (single)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", lambda m: stash(f"<em>{_escape(m.group(1))}</em>"), text)
    text = re.sub(r"(?<!_)_([^_\n]+)_(?!_)", lambda m: stash(f"<em>{_escape(m.group(1))}</em>"), text)

    # Escape remaining text
    text = _escape(text)

    # Restore placeholders
    def unstash(m: re.Match[str]) -> str:
        return placeholders[int(m.group(1))]

    text = re.sub(r"\x00(\d+)\x00", unstash, text)
    return text


def _is_callout_blockquote(lines: list[str]) -> tuple[str, list[str]] | None:
    """Detect GitHub-style alert: > [!NOTE] / > [!TIP] / etc."""
    if not lines:
        return None
    first = lines[0].lstrip()
    m = re.match(r"^>\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*$", first)
    if not m:
        return None
    kind = CALLOUT_TYPES[m.group(1)]
    body_lines = []
    for ln in lines[1:]:
        body_lines.append(re.sub(r"^>\s?", "", ln))
    return kind, body_lines


def _render_blockquote(lines: list[str]) -> str:
    callout = _is_callout_blockquote(lines)
    if callout:
        kind, body_lines = callout
        body_html = _markdown_to_html("\n".join(body_lines))
        label = kind.upper()
        return (
            f'<div class="callout callout--{kind}">'
            f'<div class="callout__label">{label}</div>'
            f'{body_html}</div>'
        )
    body = "\n".join(re.sub(r"^>\s?", "", ln) for ln in lines)
    return f"<blockquote>{_markdown_to_html(body)}</blockquote>"


def _render_list(lines: list[str], ordered: bool) -> str:
    items: list[str] = []
    current: list[str] = []
    item_re = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+(.*)$")
    for ln in lines:
        m = item_re.match(ln)
        if m:
            if current:
                items.append("\n".join(current))
            current = [m.group(1)]
        else:
            current.append(ln.strip())
    if current:
        items.append("\n".join(current))
    tag = "ol" if ordered else "ul"
    rendered = "\n".join(f"<li>{_inline(item)}</li>" for item in items)
    return f"<{tag}>\n{rendered}\n</{tag}>"


def _markdown_to_html(md: str) -> str:
    """Minimal Markdown → HTML conversion. Handles the constructs Writers Room
    articles use; for richer needs install the `markdown` package."""
    lines = md.split("\n")
    out: list[str] = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # Blank line — skip
        if not stripped:
            i += 1
            continue

        # Fenced code block
        if stripped.startswith("```"):
            lang = stripped[3:].strip()
            i += 1
            code_lines = []
            while i < n and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # consume closing fence
            code = _escape("\n".join(code_lines))
            cls = f' class="language-{_escape(lang)}"' if lang else ""
            out.append(f"<pre><code{cls}>{code}</code></pre>")
            continue

        # ATX heading
        m = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", stripped)
        if m:
            level = len(m.group(1))
            content = _inline(m.group(2))
            out.append(f"<h{level}>{content}</h{level}>")
            i += 1
            continue

        # Horizontal rule
        if re.match(r"^(\*\s*\*\s*\*+|-\s*-\s*-+|_\s*_\s*_+)\s*$", stripped):
            out.append("<hr>")
            i += 1
            continue

        # Blockquote (collect contiguous > lines)
        if stripped.startswith(">"):
            quote_lines = []
            while i < n and lines[i].strip().startswith(">"):
                quote_lines.append(lines[i])
                i += 1
            out.append(_render_blockquote(quote_lines))
            continue

        # List (unordered or ordered) — collect contiguous list lines
        if re.match(r"^\s*(?:[-*+]|\d+\.)\s+", line):
            ordered = bool(re.match(r"^\s*\d+\.\s+", line))
            list_lines = []
            while i < n and re.match(r"^\s*(?:[-*+]|\d+\.)\s+", lines[i]):
                list_lines.append(lines[i])
                i += 1
            out.append(_render_list(list_lines, ordered))
            continue

        # HTML block — pass through verbatim, preserve original line breaks.
        # Detected by an opening block-level tag at the start of a line.
        m = HTML_BLOCK_OPEN_RE.match(stripped)
        if m:
            tag = m.group(1).lower()
            close_tag = f"</{tag}>"
            block_lines = [line]
            closed_in_first = close_tag.lower() in line.lower()
            i += 1
            if not closed_in_first:
                while i < n:
                    block_lines.append(lines[i])
                    if close_tag.lower() in lines[i].lower():
                        i += 1
                        break
                    i += 1
            out.append("\n".join(block_lines))
            continue

        # Paragraph (collect until blank line or block-starter)
        para_lines = [stripped]
        i += 1
        while i < n:
            nxt = lines[i]
            if not nxt.strip():
                break
            if re.match(r"^(#{1,6}\s+|>|```|\s*(?:[-*+]|\d+\.)\s+)", nxt):
                break
            if re.match(r"^(\*\s*\*\s*\*+|-\s*-\s*-+)\s*$", nxt.strip()):
                break
            para_lines.append(nxt.strip())
            i += 1
        para = " ".join(para_lines)
        out.append(f"<p>{_inline(para)}</p>")

    return "\n".join(out)


# Block-level HTML tags whose contents MUST pass through unchanged. These tags are
# either missing from python-markdown's hardcoded block-level list (svg, figure,
# canvas, picture) or carry attribute soup that the lib mangles (video, audio).
# Without this preprocessor, python-markdown wraps <svg> in <p> and turns its
# internal newlines into <br />, breaking the schema visually.
_PRESERVE_BLOCK_TAGS = ("svg", "figure", "video", "audio", "canvas", "picture")
_PRESERVE_BLOCK_RE = re.compile(
    r"<(" + "|".join(_PRESERVE_BLOCK_TAGS) + r")\b[^>]*>.*?</\1>",
    re.DOTALL | re.IGNORECASE,
)
_PRESERVE_PLACEHOLDER = "WRPRESERVE{idx}MARKER"


def markdown_to_html(md: str) -> str:
    """Convert markdown to HTML, preferring the `markdown` package if installed.

    Pre/post-processes block-level tags that python-markdown does not recognize
    (svg, figure, video, audio, canvas, picture). Each match is replaced with a
    placeholder before the markdown pass, and restored verbatim after — so the
    raw HTML reaches the final document untouched.
    """
    preserved: list[str] = []

    def stash(m: re.Match[str]) -> str:
        preserved.append(m.group(0))
        return "\n\n" + _PRESERVE_PLACEHOLDER.format(idx=len(preserved) - 1) + "\n\n"

    md_safe = _PRESERVE_BLOCK_RE.sub(stash, md)

    try:
        import markdown as md_lib  # type: ignore

        # Use sane defaults; extras give us tables, fenced code, footnotes, attr_list
        html_out = md_lib.markdown(
            md_safe, extensions=["extra", "tables", "fenced_code", "sane_lists"]
        )
    except ImportError:
        html_out = _markdown_to_html(md_safe)

    # Restore preserved blocks. The markdown lib may wrap the placeholder in <p>...
    # match both the wrapped and bare forms.
    for idx, raw in enumerate(preserved):
        token = _PRESERVE_PLACEHOLDER.format(idx=idx)
        html_out = html_out.replace(f"<p>{token}</p>", raw)
        html_out = html_out.replace(token, raw)

    return html_out


# ---------------------------------------------------------------------------
# HTML document assembly
# ---------------------------------------------------------------------------

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
{meta_tag}
{jsonld_block}
<style>
{css}
</style>
</head>
<body>
<main>
{meta_block}
{body}
</main>
</body>
</html>
"""


def build_html(
    body_html: str,
    title: str,
    meta_description: str,
    css: str,
    lang: str = "en",
    jsonld: dict[str, Any] | None = None,
    meta_block: str = "",
) -> str:
    meta_tag = f'<meta name="description" content="{html.escape(meta_description, quote=True)}">' if meta_description else ""
    jsonld_block = ""
    if jsonld:
        jsonld_block = f'<script type="application/ld+json">\n{json.dumps(jsonld, indent=2, ensure_ascii=False)}\n</script>'
    return HTML_TEMPLATE.format(
        lang=html.escape(lang, quote=True),
        title=html.escape(title or "Article", quote=False),
        meta_tag=meta_tag,
        jsonld_block=jsonld_block,
        css=css,
        meta_block=meta_block,
        body=body_html,
    ).strip()


# ---------------------------------------------------------------------------
# Config loading (subset — same shape as check_article.py)
# ---------------------------------------------------------------------------

def load_config(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yml", ".yaml"}:
        try:
            import yaml  # type: ignore

            return yaml.safe_load(text) or {}
        except ImportError:
            print(
                f"warning: PyYAML not installed; ignoring {path}",
                file=sys.stderr,
            )
            return {}
    if path.suffix.lower() == ".json":
        return json.loads(text)
    return {}


# ---------------------------------------------------------------------------
# Auto-open helper
# ---------------------------------------------------------------------------

def open_in_browser(path: Path) -> None:
    abs_path = path.resolve()
    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(str(abs_path))  # type: ignore[attr-defined]
        elif system == "Darwin":
            subprocess.run(["open", str(abs_path)], check=False)
        else:
            subprocess.run(["xdg-open", str(abs_path)], check=False)
    except Exception as e:
        print(f"warning: could not auto-open {abs_path}: {e}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("article", type=Path, help="Path to the Markdown article")
    ap.add_argument("--output", "-o", type=Path, required=True, help="Path for the output HTML file")
    ap.add_argument("--config", type=Path, default=None, help="Path to YAML or JSON config")
    ap.add_argument("--css", type=Path, default=None, help="Path to a CSS file to inline (overrides default)")
    ap.add_argument("--title", default=None, help="HTML <title> (defaults to first H1 of the article)")
    ap.add_argument("--meta", default=None, help="HTML meta description")
    ap.add_argument("--lang", default=None, help="HTML lang attribute (defaults to config.language or 'en')")
    ap.add_argument("--jsonld", type=Path, default=None, help="Path to a JSON-LD file to embed in <head>")
    ap.add_argument("--show-meta", action="store_true", help="Render a labelled preview block above the article showing 'Title:' and 'Meta description:'")
    ap.add_argument("--open", action="store_true", help="Open the output HTML in the default browser when done")
    args = ap.parse_args()

    if not args.article.exists():
        print(f"error: article not found: {args.article}", file=sys.stderr)
        return 2

    md = args.article.read_text(encoding="utf-8-sig")
    cfg = load_config(args.config)

    # Resolve title
    title = args.title
    if not title:
        m = re.search(r"^#\s+(.+?)\s*$", md, re.MULTILINE)
        title = m.group(1).strip() if m else "Article"

    # Resolve language
    lang = args.lang or cfg.get("language") or "en"
    if lang == "auto":
        # Heuristic: French if accented chars and common French stopwords are present
        fr_signals = sum(md.lower().count(w) for w in [" le ", " la ", " les ", " des ", " une "])
        en_signals = sum(md.lower().count(w) for w in [" the ", " and ", " for ", " with ", " that "])
        lang = "fr" if fr_signals > en_signals else "en"

    # Resolve CSS
    if args.css and args.css.exists():
        css = args.css.read_text(encoding="utf-8")
    else:
        css = DEFAULT_CSS

    # Optional JSON-LD
    jsonld = None
    if args.jsonld and args.jsonld.exists():
        jsonld = json.loads(args.jsonld.read_text(encoding="utf-8"))

    # Optional labelled preview block above the article (Title + Meta description)
    meta_block = ""
    if args.show_meta:
        rows = []
        if title:
            rows.append(
                '<div class="preview-meta__row">'
                '<span class="preview-meta__label">Title :</span>'
                f'<span class="preview-meta__value">{html.escape(title, quote=False)}</span>'
                '</div>'
            )
        if args.meta:
            rows.append(
                '<div class="preview-meta__row">'
                '<span class="preview-meta__label">Meta description :</span>'
                f'<span class="preview-meta__value">{html.escape(args.meta, quote=False)}</span>'
                '</div>'
            )
        if rows:
            meta_block = '<div class="preview-meta">' + "".join(rows) + '</div>'

    # Convert markdown
    body_html = markdown_to_html(md)

    # Assemble
    full_html = build_html(
        body_html=body_html,
        title=title,
        meta_description=args.meta or "",
        css=css,
        lang=lang,
        jsonld=jsonld,
        meta_block=meta_block,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full_html, encoding="utf-8")
    print(f"wrote {args.output} ({args.output.stat().st_size:,} bytes)")

    if args.open:
        open_in_browser(args.output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
