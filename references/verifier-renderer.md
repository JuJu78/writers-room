# Verifier and renderer integration

Detailed CLI contracts for the two Python utilities the Coordinator runs after
the editorial pipeline. The high-level pipeline overview lives in `SKILL.md`;
this file documents the exact arguments, behavior and corrective-loop policy.

## Step 11 — programmatic verification

After step 10 (Coherence) and before step 13 (Publication & SEO), the
Coordinator runs:

```bash
python verifiers/check_article.py path/to/article.md --config config.yml
```

The verifier outputs JSON with pass/fail for every measurable rule. The
Coordinator must include this JSON verbatim in the **Verifier output** section
of the final delivery.

### Corrective loop policy

If any check fails:

- Identify which agent owns the failing rule (e.g., paragraph length → Readability, link balance → Link Balance)
- Re-invoke that agent with the verifier's failure list as input
- Re-run the verifier
- Stop after **one** corrective loop and surface remaining failures honestly

The Coordinator never delivers an article that fails the verifier without
explicitly flagging the failure to the user.

## Step 15 — HTML rendering

After publication metadata (step 13) and the conditional design extraction
(step 14), the Coordinator renders the HTML preview:

```bash
python verifiers/render_html.py path/to/article.md \
  -o path/to/article.html \
  --config config.yml \
  [--css path/to/derived.css] \
  --title "<title_from_seo_agent>" \
  --meta "<meta_from_seo_agent>" \
  --lang <language> \
  --show-meta \
  [--open]
```

### Argument rules

- Pass `--css` only if step 14 produced one (i.e. `design.reference_type != default`).
- Pass `--open` only if `output.auto_open_html` is true.
- If `output.format` is `markdown-only`, skip this step entirely.
- If `output.format` is `html-only`, do not silently delete the `.md` — keep both files unless the user explicitly asks to remove the markdown.

### Renderer behavior

The renderer:

- converts Markdown to semantic HTML (uses the `markdown` Python package if installed, otherwise a built-in minimal converter)
- supports GitHub-style alerts: `> [!NOTE]`, `> [!TIP]`, `> [!WARNING]`, `> [!CAUTION]`, `> [!IMPORTANT]`
- inlines the resolved CSS in `<style>`
- builds a complete `<head>` with charset, viewport, title, meta description
- embeds the JSON-LD from the SEO agent if provided via `--jsonld`
- writes a single self-contained HTML file
- opens it in the default browser when `--open` is passed
