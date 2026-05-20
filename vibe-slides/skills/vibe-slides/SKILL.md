---
name: vibe-slides
description: "Author academic slide decks in a two-phase workflow: collaborate with the user on a markdown outline (content-first, style-agnostic), then have the agent compile it to a .pptx by composing a project-specific component library over pptxgenjs, with a theme extracted from the user's template. Trigger whenever the user wants to build a deck this way — keywords: 'vibe slides', 'slides from markdown', 'academic pptx', or any /vibe-slides:theme-extractor, /vibe-slides:component-extractor, /vibe-slides:author, /vibe-slides:build-slides invocation."
---

# vibe-slides

Author academic slide decks in two decoupled phases:

1. **Content phase** — iterate on a markdown outline with the user. Nothing about styling. Just slide structure, text, and which components go where.
2. **Build phase** — agent reads the markdown, the project's `theme.json`, and the project's `components/` library, then writes a pptxgenjs script that renders the final `.pptx`.

Styling lives in a template the user provides once. The skill extracts a `theme.json` (colors, fonts, sizes) and one or more reusable components (callouts, arrows, stat blocks, …) from that template. After extraction, markdown can reference components symbolically — `::callout variant=info title="..."` — and the build phase realizes them.

---

## Commands

This is a Claude Code plugin. Slash commands are namespaced under `/vibe-slides:` and routed by Claude Code directly — this skill does not dispatch internally.

| Command | Purpose |
|---|---|
| `/vibe-slides:theme-extractor <template.pptx>` | Extract colors, fonts, sizes, spacing from a pptx template into `theme.json`. See [commands/theme-extractor.md](../../commands/theme-extractor.md). |
| `/vibe-slides:component-extractor <demo.pptx>` | Extract reusable visual components from a pptx into `components/*.js` with a manifest. See [commands/component-extractor.md](../../commands/component-extractor.md). |
| `/vibe-slides:author` | Collaborate with the user to author/iterate on `slides.md`. See [commands/author.md](../../commands/author.md). |
| `/vibe-slides:build-slides` | Compile `slides.md` to `out.pptx` by writing and running a pptxgenjs script. See [commands/build-slides.md](../../commands/build-slides.md). |

If the user describes a vibe-slides task in natural language (no slash command), this skill auto-triggers via its `description`. Default to the authoring flow in [commands/author.md](../../commands/author.md) unless the request is clearly a build/extract.

---

## Project layout

Each presentation lives in its own directory (user creates it manually — the skill does not scaffold projects):

```
./my-talk/
├── theme.json              ← produced by theme-extractor
├── components/
│   ├── callout.js          ← each component is a JS module
│   ├── arrow.js
│   ├── stat.js
│   ├── _manifest.json      ← component catalog: names, params, summaries
│   └── previews/*.png      ← per-component preview images
├── vibe-slides.md          ← project style rules (copied from skill template,
│                              customized by the user). Named this way to
│                              avoid colliding with a host repo's CLAUDE.md.
├── slides.md               ← iterated during the authoring phase
├── build.js                ← written by the agent during build
└── out.pptx                ← final output
```

`build.js` requires `lib/render_helpers.js` from this plugin's install dir (the agent substitutes the absolute path at build time — see [commands/build-slides.md](../../commands/build-slides.md)). The plugin's own files stay in the plugin; nothing is copied into the project.

Everything except this plugin and the example component library is per-project. The plugin itself is stateless.

---

## Required reading (by phase)

| Working on… | Must read |
|---|---|
| Extracting a theme | [commands/theme-extractor.md](../../commands/theme-extractor.md) |
| Extracting components | [commands/component-extractor.md](../../commands/component-extractor.md) |
| Authoring markdown | [commands/author.md](../../commands/author.md) + [schema/markdown-schema.md](../../schema/markdown-schema.md) |
| Building a deck | [commands/build-slides.md](../../commands/build-slides.md) + [experiences.md](../../experiences.md) + the project's `vibe-slides.md` + `theme.json` + `components/_manifest.json` |

Always read the project's `vibe-slides.md` during a build — it carries style constraints the user has chosen for this specific deck. (Named this way so a host repo's own `CLAUDE.md` is untouched.)

---

## Dependencies

- Python 3.12+ with `python-pptx` (for extract_theme.py / extract_components.py)
- Node.js with `pptxgenjs` installed globally (for building)
- Optional: LibreOffice (`soffice`) and Poppler (`pdftoppm`) for visual QA

pptxgenjs API reference: reuse the existing `pptx` skill's `pptxgenjs.md` — do not re-document its API here. Path: `~/.claude/skills/pptx/pptxgenjs.md`.

---

## Design principles

- **Markdown is style-agnostic.** Authoring never mentions colors, fonts, or coordinates. Only structure, content, and symbolic component references.
- **Components parameterize variation.** A good component exposes params that capture the kinds of variation you actually want (variant color, size, title text) — not low-level geometry.
- **The theme is the only place colors live.** Components and build.js read `theme.json`; nothing hardcodes hex.
- **The build agent has aesthetic latitude but not free rein.** It can add repeating motifs (e.g., a numbered-circle treatment on every step of a flow), pick which component variant fits a slide, and decide layout on canvas slides — but it stays within the rules declared in the project's `vibe-slides.md`.
- **One-pass visual QA is mandatory.** After rendering, convert to images, inspect with a subagent (fresh eyes), fix, re-verify.
