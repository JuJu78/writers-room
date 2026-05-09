# Writers Room

Turn a topic or brief into a publication-ready web article through an editorial workshop of specialized sub-agents — coordinated by a chief editor, verified by a Python checker.

A Claude Code skill. Compatible with the Claude Agent SDK.

---

## Why this skill exists

A single-prompt article writer produces text that *looks* publishable but stays weak on the things that actually matter once an editor reads it: filler paragraphs, generic plans, weak sources, drifting voice, link policies invented on the fly, "Introduction" / "Conclusion" subheadings, and a model auto-declaring "yes" to its own quality checks.

Writers Room fixes those failure modes structurally:

- **Real multi-agent orchestration.** Each sub-agent is a separate `Task` invocation with its own clean context — not a role inside one giant prompt. Quality-control passes (style, readability, semantic) run in parallel.
- **Programmatic verification.** A Python script (`verifiers/check_article.py`) measures paragraph lengths, sentence lengths, internal vs external link counts, banned characters and phrases, and heading hierarchy. The coordinator must keep editing until the checker passes.
- **HTML preview that auto-opens.** A second Python script (`verifiers/render_html.py`) converts the final Markdown into a self-contained HTML file with embedded CSS and opens it in the browser. You see the article *as a reader will*, not as raw markdown.
- **Design matching.** Pass a CSS file, an HTML page from your site, a screenshot, or just a URL — a Design Extraction agent derives a CSS file the renderer inlines. The article inherits your visual language without manual styling.
- **Configurable, not opinionated.** Voice, tone, length thresholds, banned phrases, link policy and site context are all in `config.yml`. No site, brand, or author voice is hardcoded.

---

## Installation

### Option A — git clone

```bash
git clone https://github.com/JuJu78/writers-room.git ~/.claude/skills/writers-room
```

### Option B — manual

1. Create the skill folder:

   ```bash
   mkdir -p ~/.claude/skills/writers-room
   ```

2. Copy `SKILL.md`, `config.example.yml` and `verifiers/check_article.py` into it.

3. Restart Claude Code.

### Configuration

Copy the example config:

```bash
cp ~/.claude/skills/writers-room/config.example.yml ~/.claude/skills/writers-room/config.yml
```

Edit it to match your voice, length policy and site URL. Every field is optional — defaults apply if you leave a key out.

PyYAML is recommended for the verifier:

```bash
pip install pyyaml
```

If PyYAML is not installed, the verifier falls back to defaults and prints a warning.

---

## Usage

Trigger the skill with one of:

- `write a complete article on …`
- `draft a publishable article about …`
- `crée un article SEO sur …`
- `rédige un article complet sur …`

Example:

> Draft a publishable article on internal linking strategies for B2B SaaS blogs. Primary term: internal linking. Audience: SEO managers. Tone: expert, pedagogical.

The skill will:

1. Confirm your site URL (asks once if `config.yml` doesn't define `site.base_url`).
2. Load your config.
3. Run the editorial pipeline — research, intent, plan, draft, parallel quality passes, internal/external linking, link audit, coherence read.
4. Run the Python verifier and re-edit if any rule fails.
5. Generate Title, meta description, slug and excerpt.
6. Run Design Extraction if `design.reference_type` is not `default`, producing a derived CSS file.
7. Render the final HTML, embed the CSS, and (if `output.auto_open_html` is true) open it in your default browser.
8. Deliver both files (`article.md` + `article.html`) plus a quality report including the verifier's JSON and a summary of the derived design tokens.

---

## What the skill produces

```markdown
# Editorial brief retained
- Topic / Site / Primary term / Intent / Audience / Mode

# Final article
[full article in Markdown, with internal and external links integrated inline]

# Publication metadata
- Title, Meta description, Slug, Excerpt

# Sources & credibility notes

# Integrated links
- Internal: URL — anchor
- External: URL — anchor — source

# Verifier output
[JSON from check_article.py]

# Quality report
[summary of every check, status: ready / ready after manual checks / needs rework]
```

---

## The pipeline

```
 1. Brief intake & site check        → Coordinator
 2. Research (optional web)          → Task: Research agent
 3. Reader intent & promise          → Task: Intent agent
 4. Plan & architecture              → Task: Plan agent
 5. First draft                      → Task: Writing agent
 6. Parallel quality passes          → Task: Style + Readability + Semantic (parallel)
 7. Internal linking                 → Task: Internal-links agent
 8. External sourcing                → Task: External-links agent
 9. Link balance audit               → Task: Link-balance agent
10. Coherence read-through           → Task: Coherence agent
11. Programmatic verification        → Bash: python verifiers/check_article.py
12. Corrective pass if needed        → Coordinator re-runs failing agent
13. Publication metadata             → Task: Publication-SEO agent
14. Design extraction (conditional)  → Task: Design-Extraction agent
15. HTML rendering                   → Bash: python verifiers/render_html.py
16. Final assembly + quality report  → Coordinator (auto-opens HTML if configured)
```

Sub-agent prompts are defined in `SKILL.md`. Each runs in its own `Task` context with only the slice of state it needs.

---

## Configuration reference

See `config.example.yml` for the full schema. Highlights:

| Section  | What it controls                                                         |
|----------|--------------------------------------------------------------------------|
| `voice`  | pronoun (`you-formal`, `you-informal`, `vous`, `tu`, `none`), tone       |
| `length` | max paragraph words, max sentence words, target total word range         |
| `links`  | min/max internal, max external, internal > external rule, one per para   |
| `style`  | banned characters, banned phrases, preferred lexicon, banned subheadings |
| `seo`    | title and meta length limits, slug generation                            |
| `site`   | base URL, sitemap URL, explicit list of internal pages                   |
| `design` | reference type (`default`, `css_file`, `html_file`, `screenshot`, `url`) and path/URL |
| `output` | format (`markdown-only`, `html-only`, `html-and-markdown`), auto-open, filename prefix |

The skill reads `config.yml` at session start, propagates the relevant slice to each sub-agent, and the verifier reads the same file to enforce identical rules.

---

## The verifier

Run it manually after editing:

```bash
python verifiers/check_article.py path/to/article.md --config config.yml --pretty
```

Output is a JSON report with one block per check. Exit code 0 means every check passed; 1 means at least one failed. The coordinator surfaces this output verbatim in the final delivery.

What the verifier checks:

- **Paragraph lengths** — every paragraph against `length.max_paragraph_words`.
- **Sentence lengths** — every sentence against `length.max_sentence_words` (uses a heuristic splitter that handles French and English punctuation).
- **Link policy** — internal/external counts, internal-in-range, internal > external if enabled, distinct external domains, one-link-per-paragraph rule, no footnote-style references.
- **Banned characters** — em-dash, en-dash, or anything else you list.
- **Banned phrases** — case-insensitive substring match.
- **Subheadings** — first and last subheading not in the banned list.
- **Heading hierarchy** — exactly one H1, no skipped levels.

Code blocks (fenced and inline) are excluded from length and banned-character checks.

---

## HTML output and design matching

By default the skill renders a self-contained HTML preview using an editorial-neutral CSS — clean typography, blue accent, max-width 680px, dark mode auto, mobile responsive. The HTML opens in your default browser when the session ends so you can read the article *as a reader will*.

You can also point the skill at a visual reference and an agent will derive a CSS that matches it. Set `design.reference_type` in `config.yml`:

| `reference_type` | `reference_path` example                          | What happens                                                                 |
|------------------|---------------------------------------------------|-------------------------------------------------------------------------------|
| `default`        | (empty)                                           | Use the built-in editorial-neutral CSS                                        |
| `css_file`       | `./design/blog.css`                               | Inline this CSS file as-is                                                    |
| `html_file`      | `./samples/existing-article.html`                 | Read the file, extract design tokens, write a matching CSS                    |
| `screenshot`     | `./design/article-mock.png`                       | Read the image (vision), infer tokens, write a matching CSS                   |
| `url`            | `https://my-blog.com/some-article`                | Fetch the URL, extract or infer tokens, write a matching CSS                  |

The Design Extraction agent always writes a CSS that uses the same custom property names and selectors as the default, so the renderer's HTML structure remains compatible. You can inspect or hand-edit the derived CSS before publishing.

### GitHub-style alerts

The renderer recognizes these blockquote markers and styles them as colored callouts:

```markdown
> [!NOTE]
> Generic informational callout.

> [!TIP]
> Actionable advice.

> [!WARNING]
> Something to watch out for.

> [!CAUTION]
> Critical risk.
```

### Manual rendering

You can run the renderer outside the skill:

```bash
python verifiers/render_html.py article.md \
  -o article.html \
  --config config.yml \
  --css derived.css \
  --title "My title" \
  --meta "My meta description" \
  --show-meta \
  --open
```

`--open` triggers `start` (Windows), `open` (macOS) or `xdg-open` (Linux) on the rendered file.

For richer Markdown features (tables, footnotes), install the `markdown` package: `pip install markdown`. The renderer auto-detects it.

---

## When NOT to use this skill

- A short answer to a factual question
- A single-sentence rewrite
- A translation
- A summary
- A definition
- Any partial edit that doesn't need a full editorial pipeline

The skill is heavy by design. Triggering it for a one-paragraph fix wastes context.

---

## Modes — self-extending catalog

Writers Room ships with one base mode: `informational-article` — a structured SEO blog post with inverted-pyramid layout, 1200–1800 words, 3–5 internal links. It is selected when no other mode's triggers match the user's prompt.

When you ask for an article type the catalog doesn't know yet (tutorial, news, longform, listicle, comparison, etc.), the Coordinator generates a candidate `modes/<name>.yml` from model judgment, presents it to you, and asks:

> Activate for this run only / Persist as a new mode / Cancel?

On *"persist"*, the file is written to `modes/`. The next time you ask for that type, the skill detects it automatically — no regeneration, no second confirmation. Over time, your catalog grows to match the kinds of articles you actually publish.

### What a mode controls

Each `modes/<name>.yml` is a partial config that:

- Defines `triggers.patterns` (regex) and `triggers.keywords` for auto-detection
- Overrides selected fields of the base config (length thresholds, link policy, banned subheadings, the topic-sentence rule)
- Provides a `plan_addendum` injected into the Plan agent's prompt
- Provides a `writer_addendum` injected into the Writing agent's prompt

The orchestration layer (Coordinator, parallel passes, verifier, renderer) is mode-agnostic. Modes only steer the Plan and Writing agents.

### Authoring a mode by hand

You can write a `modes/<name>.yml` directly without going through generation. See `modes/informational-article.yml` for the complete shape and reference comments.

### Disabling auto-creation

Set `modes.on_unknown: use_default` in `config.yml` to silently fall back to the default mode whenever no trigger matches. The skill will never propose a new mode.

---

## Philosophy

A publishable article is not a text that ranks. It is a text that:

- answers a real reader intent
- is structurally readable (paragraphs, sentences, hierarchy)
- has credible, diverse sources cited inline
- carries an internal linking strategy that helps the reader and the site
- speaks in a consistent, configured voice
- avoids the giveaways of one-shot AI writing (filler transitions, generic plans, banned subheadings, hallucinated links)

Writers Room orchestrates these requirements without sacrificing editorial quality. The model writes; specialized agents enforce; the verifier blocks publication when something measurable is wrong.

---

## License

MIT — see `LICENSE`.

## Contributing

Issues and PRs welcome. Please:

- describe the editorial problem your change addresses
- ensure `config.example.yml` and `verifiers/check_article.py` stay in sync with `SKILL.md`
- add or update a section in this README if you ship a new mode or configuration key
