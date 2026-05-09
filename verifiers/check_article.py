#!/usr/bin/env python3
"""Writers Room — programmatic verifier.

Reads a Markdown article and a config (YAML or JSON), then validates structural rules
that the model would otherwise have to self-declare:

    - paragraph word counts
    - sentence word counts
    - internal vs external link counts and policy
    - banned characters and phrases
    - first/last subheading not in banned list
    - heading hierarchy (no skipped levels)
    - one-link-per-paragraph rule (internal AND external)

Outputs a JSON report on stdout. Exit code 0 if every check passes, 1 otherwise.

Usage
-----
    python check_article.py article.md
    python check_article.py article.md --config config.yml
    python check_article.py article.md --config config.json
    python check_article.py article.md --base-url https://example.com

Dependencies
------------
Standard library only, with optional PyYAML for YAML configs. If PyYAML is not
installed and a YAML config is requested, the verifier falls back to defaults
and prints a warning.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Defaults — match config.example.yml
# ---------------------------------------------------------------------------

DEFAULTS: dict[str, Any] = {
    "length": {
        "max_paragraph_words": 100,
        "max_sentence_words": 30,
    },
    "links": {
        "internal_min": 3,
        "internal_max": 5,
        "external_max": 3,
        "internal_must_exceed_external": True,
        "one_link_per_paragraph": True,
    },
    "style": {
        "banned_chars": [],
        "banned_phrases": [],
        "banned_subheadings": ["Introduction", "Conclusion", "Intro", "Outro"],
    },
    "site": {
        "base_url": "",
    },
}


# ---------------------------------------------------------------------------
# Markdown parsing
# ---------------------------------------------------------------------------

LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`]+`")
FOOTNOTE_REF_RE = re.compile(r"^\[\d+\]:\s+\S+", re.MULTILINE)
BRACKET_FOOTNOTE_RE = re.compile(r"\[[^\]]+\]\[\d+\]")


@dataclass
class Section:
    level: int
    title: str
    body: str
    paragraphs: list[str] = field(default_factory=list)


def strip_code(md: str) -> str:
    """Remove fenced and inline code so length checks ignore code blocks."""
    md = CODE_FENCE_RE.sub("", md)
    md = INLINE_CODE_RE.sub("", md)
    return md


LIST_LINE_RE = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+", re.MULTILINE)

# Block-level HTML tags. Paragraphs that begin with one of these are not prose
# and are excluded from length / banned-pattern checks.
HTML_BLOCK_TAGS = (
    "svg", "figure", "div", "table", "aside", "details", "section", "nav",
    "video", "audio", "iframe", "script", "style", "blockquote",
    "address", "article", "footer", "header", "main", "form", "canvas", "picture",
)
HTML_BLOCK_OPEN_RE = re.compile(
    r"^\s*<(" + "|".join(HTML_BLOCK_TAGS) + r")\b", re.IGNORECASE
)


def is_html_block(p: str) -> bool:
    """A paragraph is an HTML block if it starts with a known block-level tag."""
    return bool(HTML_BLOCK_OPEN_RE.match(p))


def is_list_block(p: str) -> bool:
    """A paragraph is a list block if every non-empty line is a list item."""
    lines = [ln for ln in p.splitlines() if ln.strip()]
    if not lines:
        return False
    return all(LIST_LINE_RE.match(ln) for ln in lines)


def split_paragraphs(text: str) -> list[str]:
    """Split on blank lines, drop pure-heading paragraphs, expand list blocks
    into one paragraph per item (so each item is checked individually)."""
    raw = re.split(r"\n\s*\n", text)
    paragraphs = []
    for p in raw:
        p = p.strip()
        if not p:
            continue
        # Skip paragraphs that are only a heading
        if re.match(r"^#{1,6}\s+", p) and "\n" not in p:
            continue
        # Skip raw HTML blocks (svg, figure, table, etc.) — they are not prose
        if is_html_block(p):
            continue
        if is_list_block(p):
            for ln in p.splitlines():
                ln = LIST_LINE_RE.sub("", ln).strip()
                if ln:
                    paragraphs.append(ln)
        else:
            paragraphs.append(p)
    return paragraphs


def split_sentences(text: str) -> list[str]:
    """Crude sentence splitter — good enough for word-count checks."""
    text = re.sub(r"\s+", " ", text).strip()
    # Split on ., !, ? followed by whitespace + capital or end-of-string
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-ÖØ-Þ])", text)
    return [s.strip() for s in sentences if s.strip()]


def word_count(text: str) -> int:
    """Count words, ignoring markdown link syntax."""
    plain = LINK_RE.sub(r"\1", text)
    plain = re.sub(r"[#*_>`-]", " ", plain)
    return len(re.findall(r"\b\w+\b", plain, flags=re.UNICODE))


def parse_sections(md: str) -> list[Section]:
    """Split the article into sections by H2 (## ...) primarily."""
    sections: list[Section] = []
    matches = list(HEADING_RE.finditer(md))
    if not matches:
        # No headings — treat the whole thing as one section
        return [Section(level=0, title="(no heading)", body=md, paragraphs=split_paragraphs(md))]

    for i, m in enumerate(matches):
        level = len(m.group(1))
        title = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(md)
        body = md[start:end].strip()
        sec = Section(level=level, title=title, body=body, paragraphs=split_paragraphs(body))
        sections.append(sec)
    return sections


def extract_links(md: str) -> list[dict[str, Any]]:
    """Return a list of {anchor, url, paragraph_index} for every Markdown link."""
    paragraphs = split_paragraphs(md)
    links = []
    for idx, p in enumerate(paragraphs):
        for m in LINK_RE.finditer(p):
            links.append(
                {
                    "anchor": m.group(1),
                    "url": m.group(2).strip(),
                    "paragraph_index": idx,
                }
            )
    return links


def is_internal(url: str, base_url: str) -> bool:
    if not base_url:
        # Without a base URL we cannot tell — treat absolute URLs as external,
        # relative URLs as internal
        return not url.startswith(("http://", "https://"))
    base_host = urlparse(base_url).netloc.lower()
    target_host = urlparse(url).netloc.lower()
    if not target_host:
        return True  # relative link → internal
    return target_host == base_host or target_host.endswith("." + base_host)


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def load_config(path: Path | None) -> dict[str, Any]:
    """Load config from YAML or JSON, deep-merge over DEFAULTS."""
    cfg = json.loads(json.dumps(DEFAULTS))  # deep copy
    if path is None or not path.exists():
        return cfg

    text = path.read_text(encoding="utf-8")
    user_cfg: dict[str, Any] | None = None

    if path.suffix.lower() in {".yml", ".yaml"}:
        try:
            import yaml  # type: ignore

            user_cfg = yaml.safe_load(text)
        except ImportError:
            print(
                f"warning: PyYAML not installed; ignoring {path} and using defaults",
                file=sys.stderr,
            )
            return cfg
    elif path.suffix.lower() == ".json":
        user_cfg = json.loads(text)
    else:
        print(f"warning: unknown config format {path.suffix}; using defaults", file=sys.stderr)
        return cfg

    if user_cfg:
        deep_merge(cfg, user_cfg)
    return cfg


def deep_merge(target: dict[str, Any], source: dict[str, Any]) -> None:
    for k, v in source.items():
        if k in target and isinstance(target[k], dict) and isinstance(v, dict):
            deep_merge(target[k], v)
        else:
            target[k] = v


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_paragraph_lengths(md: str, max_words: int) -> dict[str, Any]:
    paragraphs = split_paragraphs(strip_code(md))
    over = []
    for i, p in enumerate(paragraphs):
        wc = word_count(p)
        if wc > max_words:
            over.append({"index": i, "words": wc, "preview": p[:120]})
    return {
        "rule": "max_paragraph_words",
        "limit": max_words,
        "violations": over,
        "pass": not over,
    }


def check_sentence_lengths(md: str, max_words: int) -> dict[str, Any]:
    paragraphs = split_paragraphs(strip_code(md))
    over = []
    for pi, p in enumerate(paragraphs):
        for si, s in enumerate(split_sentences(p)):
            wc = word_count(s)
            if wc > max_words:
                over.append({"paragraph": pi, "sentence": si, "words": wc, "preview": s[:120]})
    return {
        "rule": "max_sentence_words",
        "limit": max_words,
        "violations": over,
        "pass": not over,
    }


def check_links(md: str, base_url: str, link_cfg: dict[str, Any]) -> dict[str, Any]:
    links = extract_links(strip_code(md))
    internal = [link for link in links if is_internal(link["url"], base_url)]
    external = [link for link in links if not is_internal(link["url"], base_url)]

    issues = []

    in_range = link_cfg["internal_min"] <= len(internal) <= link_cfg["internal_max"]
    if not in_range:
        issues.append(
            f"internal links count {len(internal)} not in "
            f"[{link_cfg['internal_min']}, {link_cfg['internal_max']}]"
        )

    if len(external) > link_cfg["external_max"]:
        issues.append(f"external links count {len(external)} exceeds {link_cfg['external_max']}")

    if link_cfg["internal_must_exceed_external"] and len(internal) <= len(external):
        issues.append(
            f"internal ({len(internal)}) must exceed external ({len(external)})"
        )

    # Distinct external domains
    ext_domains = [urlparse(link["url"]).netloc.lower() for link in external]
    dup_domains = [d for d in set(ext_domains) if ext_domains.count(d) > 1]
    if dup_domains:
        issues.append(f"duplicate external domains: {sorted(dup_domains)}")

    # One link per paragraph (per type)
    if link_cfg["one_link_per_paragraph"]:
        from collections import Counter

        int_per_para = Counter(link["paragraph_index"] for link in internal)
        ext_per_para = Counter(link["paragraph_index"] for link in external)
        for pi, count in int_per_para.items():
            if count > 1:
                issues.append(f"paragraph {pi} contains {count} internal links")
        for pi, count in ext_per_para.items():
            if count > 1:
                issues.append(f"paragraph {pi} contains {count} external links")

    # Footnote-style references
    if FOOTNOTE_REF_RE.search(md):
        issues.append("footnote-style references like [1]: URL detected — must be inline")
    if BRACKET_FOOTNOTE_RE.search(md):
        issues.append("bracketed footnote citations like [text][1] detected — must be inline")

    return {
        "rule": "link_policy",
        "internal_count": len(internal),
        "external_count": len(external),
        "internal_in_range": in_range,
        "internal_links": internal,
        "external_links": external,
        "issues": issues,
        "pass": not issues,
    }


def check_banned_chars(md: str, banned: list[str]) -> dict[str, Any]:
    md_clean = strip_code(md)
    found = []
    for ch in banned:
        count = md_clean.count(ch)
        if count > 0:
            found.append({"char": ch, "count": count})
    return {
        "rule": "banned_chars",
        "banned": banned,
        "found": found,
        "pass": not found,
    }


def check_banned_phrases(md: str, banned: list[str]) -> dict[str, Any]:
    md_clean = strip_code(md).lower()
    found = []
    for phrase in banned:
        count = md_clean.count(phrase.lower())
        if count > 0:
            found.append({"phrase": phrase, "count": count})
    return {
        "rule": "banned_phrases",
        "banned": banned,
        "found": found,
        "pass": not found,
    }


def check_subheadings(md: str, banned: list[str]) -> dict[str, Any]:
    headings = [(len(m.group(1)), m.group(2).strip()) for m in HEADING_RE.finditer(md)]
    sub = [(level, title) for level, title in headings if level >= 2]
    issues = []
    if sub:
        first_lvl, first_title = sub[0]
        last_lvl, last_title = sub[-1]
        for label in banned:
            if first_title.lower() == label.lower():
                issues.append(f"first subheading is banned: '{first_title}'")
            if last_title.lower() == label.lower():
                issues.append(f"last subheading is banned: '{last_title}'")
    return {
        "rule": "banned_subheadings",
        "banned": banned,
        "issues": issues,
        "pass": not issues,
    }


def check_heading_hierarchy(md: str) -> dict[str, Any]:
    headings = [(len(m.group(1)), m.group(2).strip()) for m in HEADING_RE.finditer(md)]
    issues = []
    h1_count = sum(1 for level, _ in headings if level == 1)
    if h1_count == 0:
        issues.append("no H1 found")
    elif h1_count > 1:
        issues.append(f"multiple H1 headings ({h1_count}); should be exactly 1")

    prev_level = 0
    for level, title in headings:
        if prev_level and level > prev_level + 1:
            issues.append(f"skipped heading level: {prev_level} → {level} at '{title}'")
        prev_level = level

    return {
        "rule": "heading_hierarchy",
        "headings": [{"level": lv, "title": t} for lv, t in headings],
        "issues": issues,
        "pass": not issues,
    }


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def run(article_path: Path, config_path: Path | None, base_url_override: str | None) -> dict[str, Any]:
    md = article_path.read_text(encoding="utf-8-sig")
    cfg = load_config(config_path)
    base_url = base_url_override or cfg.get("site", {}).get("base_url", "")

    checks = {
        "paragraph_lengths": check_paragraph_lengths(md, cfg["length"]["max_paragraph_words"]),
        "sentence_lengths": check_sentence_lengths(md, cfg["length"]["max_sentence_words"]),
        "links": check_links(md, base_url, cfg["links"]),
        "banned_chars": check_banned_chars(md, cfg["style"]["banned_chars"]),
        "banned_phrases": check_banned_phrases(md, cfg["style"]["banned_phrases"]),
        "subheadings": check_subheadings(md, cfg["style"]["banned_subheadings"]),
        "heading_hierarchy": check_heading_hierarchy(md),
    }

    overall_pass = all(c["pass"] for c in checks.values())

    return {
        "article": str(article_path),
        "config": str(config_path) if config_path else None,
        "base_url": base_url,
        "summary": {
            "total_checks": len(checks),
            "passed": sum(1 for c in checks.values() if c["pass"]),
            "failed": sum(1 for c in checks.values() if not c["pass"]),
            "overall_pass": overall_pass,
        },
        "checks": checks,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("article", type=Path, help="Path to the Markdown article")
    ap.add_argument("--config", type=Path, default=None, help="Path to YAML or JSON config")
    ap.add_argument("--base-url", default=None, help="Override site.base_url for link classification")
    ap.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    args = ap.parse_args()

    if not args.article.exists():
        print(f"error: article not found: {args.article}", file=sys.stderr)
        return 2

    report = run(args.article, args.config, args.base_url)
    indent = 2 if args.pretty else None
    print(json.dumps(report, indent=indent, ensure_ascii=False))
    return 0 if report["summary"]["overall_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
