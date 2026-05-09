# Modes catalog

Writers Room ships with one base mode (`informational-article.yml`) and grows
its catalog as users request new article types. Every mode is a partial config
that overrides selected fields of the base config plus prompt addenda for the
Plan and Writing agents.

## Mode file shape

```yaml
name: tutorial
display_name: "Tutorial / How-to"
description: "Step-by-step instructional article."
triggers:
  patterns:                                 # regex patterns matched against the user prompt
    - '(?i)\b(tutorial|tuto|how-to|how to)\b'
    - '(?i)\b(comment (faire|configurer|installer|déployer))\b'
  keywords: ["tutorial", "tuto", "how-to", "step-by-step"]
overrides:                                   # merged over base config (mode wins on conflicts)
  length:
    max_paragraph_words: 120
    max_sentence_words: 35
    target_total_words: [1500, 3000]
  links:
    internal_max: 7
    external_max: 5
  style:
    first_sentence_is_topic_sentence: false
plan_addendum: |
  Structure: Prerequisites → numbered steps → Troubleshooting → Next steps.
  Each step's H2 begins with an imperative verb.
writer_addendum: |
  Open with prerequisites and what the reader will achieve.
  Each step starts with the action in imperative form. Code blocks have no length cap.
```

## Detection at step 1 of the pipeline

The Coordinator:

1. Lists every `modes/*.yml` file
2. Tests the user's prompt against each mode's `triggers.patterns` (regex) and `triggers.keywords`
3. Selects the first mode whose triggers match, or `modes.default` (`informational-article`) if no match
4. Deep-merges the mode's `overrides` over the base config (the mode wins on conflicts)
5. Passes `plan_addendum` to the Plan agent and `writer_addendum` to the Writing agent at their respective Task invocations

## Auto-creating a new mode

When the user explicitly asks for an article type that has no matching mode
(e.g. *"rédige une listicle"*), the Coordinator follows `modes.on_unknown`. With
the recommended `ask_to_create` setting:

1. The Coordinator generates a candidate `modes/listicle.yml` from model judgment, drawing on what it knows about the article type.
2. It prints the proposed YAML to the user verbatim.
3. It asks: *"Activate for this run only / Persist as a new mode / Cancel?"*
4. On *"persist"*, it writes the file to `modes/`. The next request matching the new triggers will run automatically without asking.
5. On *"activate for this run only"*, the override is held in memory and never written to disk.
6. On *"cancel"*, the Coordinator falls back to the default mode.

This is the **only** path by which the skill modifies its own files. Outside of
mode creation, all skill files are read-only at runtime.

If `modes.on_unknown` is set to `use_default`, no generation happens — unknown
types silently fall back to the default. If `modes.persist_new_modes` is set
to `always` (not recommended), the Coordinator skips the confirmation step and
writes immediately.
