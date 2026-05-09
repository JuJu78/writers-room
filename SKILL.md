---
name: writers-room
description: "Produce a publication-ready web article through a multi-agent editorial workshop coordinated by a chief editor. Real Task-tool sub-agent orchestration, programmatic verification via a Python checker, self-extending mode catalog (informational-article ships built-in; tutorial, news, longform and other modes are auto-generated on first request and persisted with user confirmation), persistent feedback loop. Outputs both Markdown and a self-contained HTML preview that auto-opens; design can match a CSS file, an existing HTML page, a screenshot, or a URL. MANDATORY TRIGGERS (EN): 'write a complete article', 'draft a publishable article', 'writers room', 'editorial workshop', 'produce SEO article'. MANDATORY TRIGGERS (FR): 'rédige un article', 'écris un article complet', 'writers room', 'atelier éditorial', 'crée un article SEO'. DO NOT TRIGGER on: short answers, single-sentence rewrites, translations, summaries, factual lookups, or partial content fixes. Trigger only when the user wants a full publication-ready article from a brief or topic."
---

# Writers Room

Writers Room turns a brief or topic into a complete, useful, credible, publication-ready web article through an editorial workshop of specialized sub-agents.

**Four design choices set this skill apart from a single-prompt writer:**

1. **Real multi-agent orchestration** — each sub-agent is invoked through the `Task` tool with its own clean context, not as a role inside one giant prompt. Quality-control passes (style, readability, semantic, link audit) run as separate agents and several can run in parallel.
2. **Programmatic verification** — link counts, paragraph lengths, sentence lengths, banned-pattern detection and heading hierarchy are checked by a Python script (`verifiers/check_article.py`), not by the model auto-declaring "yes/no". The coordinator must re-edit until the checker passes.
3. **HTML preview with optional design matching** — the final article is rendered to a self-contained HTML file via `verifiers/render_html.py` and opened in the browser. The visual design can either use the editorial-neutral default CSS or be derived by an agent from a reference (existing CSS file, HTML page, screenshot, or URL).
4. **Self-extending mode catalog + feedback loop** — the skill ships with one base mode (`informational-article`). When a user requests an article type that has no matching mode (tutorial, news, longform, listicle, etc.), the Coordinator generates a candidate `modes/<name>.yml`, presents it, and persists it on confirmation — so the second request of that type runs automatically. A `feedback.md` log is read at every run start and appended to at delivery; recurring notes are surfaced for manual promotion into `config.yml` hard rules.

The skill ships with neutral defaults and is fully configurable via an optional `config.yml`. No site, brand, or author voice is hardcoded.

---

## Repository layout

Progressive disclosure: this `SKILL.md` is the dispatcher. Detailed prompts and
references live in subdirectories and are loaded only when needed.

```
writers-room/
├── SKILL.md                  ← this file (dispatcher + pipeline overview)
├── config.example.yml        ← full configuration schema with comments
├── feedback.md.example       ← starter feedback log
├── modes/
│   ├── README.md             ← mode file shape + detection + auto-creation
│   └── informational-article.yml
├── prompts/                  ← one file per sub-agent prompt
│   ├── 01-research.md
│   ├── 02-intent.md
│   ├── 03-plan.md
│   ├── 04-writing.md
│   ├── 05-style.md
│   ├── 06-readability.md
│   ├── 07-semantic.md
│   ├── 08-internal-links.md
│   ├── 09-external-links.md
│   ├── 10-link-balance.md
│   ├── 11-coherence.md
│   ├── 12-publication-seo.md
│   └── 13-design-extraction.md
├── references/
│   └── verifier-renderer.md  ← CLI contracts + corrective-loop policy
└── verifiers/
    ├── check_article.py
    └── render_html.py
```

---

## When to use it

Use Writers Room when the user wants:

- a complete, publication-ready web article from a topic or brief
- a structured plan plus the final article in one session
- a full editorial pass on an existing draft headed to publication

Do **not** use it for short answers, isolated rewrites, translations, summaries, factual lookups, or partial fixes. The skill is heavy by design — invoking it for a one-paragraph edit wastes context.

---

## Configuration

Writers Room reads an optional `config.yml` file in the skill directory or
project root. If absent, neutral defaults apply.

**See `config.example.yml` for the full schema with comments.** The most
load-bearing keys are `language`, `mode`, `voice`, `length`, `links`, `style`,
`site.base_url`, `modes`, `feedback`, `design`, and `output`.

The Coordinator loads `config.yml` once at session start and propagates the
relevant slice to each sub-agent. Users can override any field per-session by
stating it in their request.

---

## Mode catalog and detection

Writers Room ships with one base mode (`informational-article`) and grows its
catalog as users request new article types. Every mode is a partial config in
`modes/<name>.yml` that overrides selected fields plus prompt addenda for the
Plan and Writing agents.

**See `modes/README.md` for the full mode file shape, the detection algorithm,
and the auto-creation flow.** In short:

- The Coordinator tests the user prompt against each `modes/*.yml`'s triggers.
- The first match wins; otherwise it falls back to `modes.default`.
- An unknown explicit type triggers the auto-creation flow with user confirmation (the only path by which the skill modifies its own files).

---

## Pipeline

```
 0. Feedback intake (if enabled)     → Coordinator reads feedback.md, extracts soft preferences
 1. Brief intake, mode detection,    → Coordinator detects article type, applies mode overrides;
    site check                         site check; auto-create new mode if needed (with confirmation)
 2. Research (optional web)          → Task: prompts/01-research.md
 3. Reader intent & promise          → Task: prompts/02-intent.md
 4. Plan & architecture              → Task: prompts/03-plan.md
 5. First draft                      → Task: prompts/04-writing.md
 6. Parallel quality passes          → Task: prompts/05-style.md + 06-readability.md + 07-semantic.md (in parallel)
 7. Internal linking                 → Task: prompts/08-internal-links.md
 8. External sourcing                → Task: prompts/09-external-links.md
 9. Link balance audit               → Task: prompts/10-link-balance.md
10. Coherence read-through           → Task: prompts/11-coherence.md
11. Programmatic verification        → Bash: python verifiers/check_article.py
12. Corrective pass if needed        → Coordinator re-runs failing agent
13. Publication metadata             → Task: prompts/12-publication-seo.md
14. Design extraction (conditional)  → Task: prompts/13-design-extraction.md
                                         (only if config.design.reference_type != default)
15. HTML rendering                   → Bash: python verifiers/render_html.py
16. Final assembly + quality report  → Coordinator (auto-opens HTML if configured)
17. Feedback collection (if enabled) → Coordinator asks user, appends dated entry to feedback.md
```

Each `Task:` line corresponds to a real `Task` tool invocation with
`subagent_type: general-purpose` and the prompt file listed. Do not collapse
multiple agents into a single Task call — the value is in clean context per role.

Steps 5–7 of the parallel block (Style, Readability, Semantic) are
independent and **must** be invoked in parallel in a single message with
three Task tool calls.

Step 14 (Design Extraction) is **conditional** — skip it entirely when
`design.reference_type` is `default`; the renderer in step 15 will use the
built-in editorial-neutral CSS.

---

## How to invoke a sub-agent

When the Coordinator (the main session) reaches a pipeline step that says
`Task: prompts/NN-<name>.md`:

1. **Read the prompt file** with the Read tool.
2. **Substitute** every `{{...}}` placeholder with the relevant slice of session state (brief, primary term, config slice, prior agent outputs, mode addenda, feedback brief).
3. **Invoke** the `Task` tool with `subagent_type: general-purpose` and the substituted prompt as the `prompt` argument.

For step 6 (parallel quality passes), the Coordinator sends **one message with
three Task calls** so they run concurrently:

```
[Task(Style), Task(Readability), Task(Semantic)]
```

The Coordinator then merges the three outputs before invoking the linking agents.

This pull-on-demand pattern means each session pays the token cost only for
the prompts of the agents it actually invokes — not all 13 up front.

---

## Coordinator behavior

The Coordinator is the main session. Its responsibilities, in order:

1. **Feedback intake** — if `feedback.enabled` is true and `feedback.path` exists, read the file. Parse the latest 3–5 entries. Extract: phrases to avoid, tone notes, structural complaints, recurring patterns flagged for promotion. Hold these as a "feedback brief" to inject into the right sub-agents in step 6. Do not auto-edit `config.yml` — promotion is the user's manual call.
2. **Intake** — read the user's brief. Identify topic, primary term, intent, audience, target length, and language.
3. **Mode detection** — list `modes/*.yml`, test their triggers against the user's prompt, select the first matching mode or `modes.default`. If the user explicitly named a type that has no matching mode and `modes.on_unknown` is `ask_to_create`, generate a candidate YAML, present it, and act on the user's choice (persist / activate-only / cancel). Apply the mode's `overrides` over the base config and stash `plan_addendum` and `writer_addendum` for the Task agents (see `modes/README.md`).
4. **Site check** — if `site.base_url` is unknown and not in `config.yml`, ask exactly once: *"Which website will the article be published on? (needed for internal linking)"*. Do not proceed without an answer or an explicit "no internal links" override.
5. **Load config** — read `config.yml` if present.
6. **Run pipeline** — invoke each Task agent per the procedure above. Pass only the slices each agent needs, plus the relevant slice of the feedback brief (e.g. Writer gets phrases to avoid + the mode's writer_addendum, Style gets tone notes, Plan gets structural complaints + the mode's plan_addendum).
7. **Run the verifier** — see `references/verifier-renderer.md` for the CLI contract and the one-loop corrective policy.
8. **Run design extraction (if needed)** — when `design.reference_type` is anything other than `default`, invoke the Design Extraction agent. It writes a CSS file the renderer will inline.
9. **Render HTML** — see `references/verifier-renderer.md` for renderer arguments and rules.
10. **Final delivery** — produce the output in the format below. Single version, no concurrent drafts. Mention both file paths (markdown and HTML).
11. **Feedback collection** — if `feedback.append_at_end` is true, ask the user: *"Anything you'd like me to remember for next time? (style, structure, sources, anything to stop or start doing)"*. Append a dated entry to `feedback.path` with the user's response, the article title, and the date. If a recurring note has appeared `feedback.promotion_hint_threshold` times across recent entries, surface it in the final report as a promotion candidate (the user manually decides whether to add it to `config.yml`).

The Coordinator never delivers an article that fails the verifier without
explicitly flagging the failure to the user.

---

## Output format

```markdown
# Editorial brief retained
- Topic:
- Site:
- Primary term:
- Intent:
- Audience:
- Mode:

# Final article

[full article in Markdown]

# Publication metadata
- Title:
- Meta description:
- Slug:
- Excerpt:

# Sources & credibility notes

# Integrated links
- Internal: [URL — anchor]
- External: [URL — anchor — source]

# Verifier output
[paste the JSON output from check_article.py]

# Quality report
- Intent covered: yes/no
- Primary term:
- Synonyms used:
- Paragraphs ≤ max words: yes/no
- Sentences ≤ max words: yes/no
- Topic sentence first (if enabled): yes/no
- Banned chars/phrases absent: yes/no
- Internal link count: N (range: min–max)
- External link count: N (max: M)
- Internal > external: yes/no
- All external sources distinct: yes/no
- First subheading not banned: yes/no
- Last subheading not banned: yes/no
- Coherence: validated/not validated
- Final status: ready / ready after manual checks / needs rework
```

---

## Verifier and renderer

Programmatic verification (step 11) and HTML rendering (step 15) are run via
two Python scripts in `verifiers/`. **See `references/verifier-renderer.md`**
for the exact CLI contracts, argument rules per `output.format`, the
one-corrective-loop policy, and renderer behavior (Markdown conversion,
GitHub-style alerts, inlined CSS, JSON-LD embedding, browser open).

---

## Notes & guarantees

- The Coordinator delivers exactly one final article. Sub-agents never deliver competing drafts.
- The skill never invents internal URLs. If the site has no exposable internal pages, the linking agent flags it and the article ships with fewer links rather than fabricated ones.
- Every claim the Writing agent could not fully back is marked `[VERIFY]` inline. The Coordinator either resolves these or flags them in the final report.
- The skill is configuration-driven. To run it for a different brand, language, or voice, change `config.yml` — never edit `SKILL.md`.
- The skill ships with one base mode (`informational-article`) and grows its catalog as users request new types. New modes are auto-generated on first request, presented to the user, and persisted on confirmation. The orchestration layer never changes; only the `modes/<name>.yml` files do.
