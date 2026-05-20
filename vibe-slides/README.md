# vibe-slides

A Claude Code plugin for authoring academic-style slide decks in two decoupled phases: collaborate with the agent on a content-only markdown outline, then have it compile to `.pptx` via pptxgenjs using a theme and component library extracted from your own template.

## Install

```
/plugin marketplace add heiyan-2020/claude-plugins
/plugin install vibe-slides@heiyan-2020
```

The marketplace at [`heiyan-2020/claude-plugins`](https://github.com/heiyan-2020/claude-plugins) is just an index — it points back to this repo. No `git clone` needed; Claude Code handles the fetch.

## Commands

| Command | When you run it |
|---|---|
| `/vibe-slides:theme-extractor <template.pptx>` | once per template — derive `theme.json` |
| `/vibe-slides:component-extractor <demo.pptx>` | (stub) bootstrap reusable components from an example |
| `/vibe-slides:author` | iterate `slides.md` interactively with the agent |
| `/vibe-slides:build-slides` | compile `slides.md` → `out.pptx` |

The skill also auto-triggers when you describe a vibe-slides task in plain English ("let's vibe-slides a deck about X"), defaulting to the authoring flow.

## Workflow

For each new deck:

1. **Once per template** — `/vibe-slides:theme-extractor my-template.pptx`. The agent parses the .pptx, dumps theme tokens, asks five focused questions (font, motif, palette, sizes, spacing), and writes `theme.json`. It also bootstraps `components/` and a starter `vibe-slides.md` from the plugin's example.
2. **Author** — in a project dir with `theme.json` + `components/`, run `/vibe-slides:author` (or just talk to the agent naturally). It writes `slides.md` in the layout-only DSL described below — never colors, coordinates, or fonts.
3. **Build** — `/vibe-slides:build-slides`. The agent reads `slides.md`, `theme.json`, `components/`, and your project's `vibe-slides.md` (style rules), generates `build.js`, runs it, and visual-QAs the output. You get `out.pptx`.
4. **Iterate** — corrections to the agent go into `vibe-slides.md` (deck-specific style rules) or the plugin's `experiences.md` (cross-deck tuning lessons).

## How it works

Authoring and styling pull in opposite directions. Bullet density, slide order, transitions are content concerns. Spacing, fills, motif geometry are style concerns. Conflating them is what makes "writing slides in code" exhausting.

So this plugin enforces a split:

- **Markdown is style-agnostic.** You write `## What we measured / - 143K LoC` and the agent decides whether that's a `bullets` slide or a `stat-row`.
- **`theme.json` is the only place colors live.** Components and `build.js` read it; nothing hardcodes hex.
- **Components parameterize variation.** A `callout` exposes `variant: info | warn | ok` rather than raw hex. The component module maps the variant onto theme keys.
- **The build agent has aesthetic latitude inside guardrails.** It picks a callout variant for the slide's tone and applies declared motifs consistently — but won't violate `vibe-slides.md`.

## The markdown DSL

Slides are separated by `---`. Each slide opens with YAML front matter declaring `layout` and any layout-specific fields, then a body in that layout's grammar.

```markdown
---
layout: title
title: A Deck About X
subtitle: With a subtitle
authors: [Alice, Bob]
---

---
layout: bullets
title: Motivation
---

- Classical verifiers need hand-written specs
- Weeks per kLoC
- LLMs change the equation

---
layout: two-column
title: Approach vs Bet
---

## The Bottleneck
- specs are slow

::column

## Our Bet
- LLM writes specs
```

Built-in layouts: `title`, `section`, `bullets`, `two-column`, `image-left` / `image-right`, `stat-row`, `canvas`. `canvas` is the escape hatch — prose describes intent, inline component references describe content:

```markdown
---
layout: canvas
title: Pipeline
---

Show the five stages left-to-right, connected by arrows.

::num_circle n=1
::callout variant=info title="Stage 1: Parse"
explain stage 1 here
::end

::arrow from=[2.7,3] to=[4.5,3]
```

Image stubs reserve a slot before the asset exists; the description survives as a speaker note in the rendered .pptx so you don't forget what's missing:

```markdown
::image-stub caption="System diagram"
A horizontal flow: parser → checker → reporter, with red badges
on the points where the LLM is invoked.
::end
```

Full grammar lives at [`schema/markdown-schema.md`](schema/markdown-schema.md).

## Per-project structure

```
my-talk/
├── theme.json              ← extracted from your template
├── components/
│   ├── callout.js
│   ├── arrow.js
│   ├── stat.js
│   ├── _manifest.json      ← component catalog: names, params, summaries
│   └── previews/*.png      ← per-component preview images
├── vibe-slides.md          ← project-specific style rules
├── slides.md               ← deck content (the only file you write by hand)
├── build.js                ← generated; rewritten on every build
└── out.pptx                ← final output
```

You write `slides.md` and curate `vibe-slides.md`. Everything else is generated or copied.

## Customization

- **`<project>/vibe-slides.md`** — deck-specific style rules. Constrains what the build agent can do (motifs to keep on, callout variants to avoid, max bullets per slide, …). The build agent reads it every build, ahead of everything else.
- **Plugin's `experiences.md`** — cross-deck agent-tuning lessons you accumulate over time ("don't ever stretch a callout past column boundary"). Binding unless the project's `vibe-slides.md` overrides. Empty in a fresh install — fill it as you go.

## Dependencies

- **Python 3.12+** with `python-pptx` — theme extraction
- **Node.js** with `pptxgenjs` installed globally — building
- *Optional:* **LibreOffice** (`soffice`) and **Poppler** (`pdftoppm`) — visual-QA pass converts the output to JPGs and feeds them to a reviewer subagent

Install once:

```bash
pip install python-pptx
npm install -g pptxgenjs
```

## Iterating on the plugin itself

If you're forking this and want a tight edit loop:

```bash
claude --plugin-dir /path/to/your/clone
```

`--plugin-dir` reads live from disk; `/reload-plugins` picks up edits. The marketplace install path is for stable use across machines, not active development.
