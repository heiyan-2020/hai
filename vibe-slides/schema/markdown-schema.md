# vibe-slides markdown schema

A deck is a single `slides.md` file. Slides are separated by a line containing only `---`. The first line of a slide is a YAML front-matter block; the rest is the slide body.

This spec is deliberately lean — it's designed for the **content** phase. Styling and coordinates live in `theme.json` and the build agent's judgment, not here.

---

## Slide structure

```markdown
---
layout: <layout-name>
title: <string, optional>
subtitle: <string, optional>
<other layout-specific params>
---

<slide body — markdown>
```

Slides separated by a line containing exactly `---`.

### Front matter rules

- `layout` is **required** on every slide.
- All other keys are optional unless the chosen layout requires them.
- Values can be strings, numbers, booleans, or lists (`[a, b, c]`).
- Use double quotes if a value contains `:`, `#`, or other YAML-special characters.

---

## Built-in layouts

These are recognized by default. Projects can add more via their `CLAUDE.md` — whatever the build agent knows to handle.

### `title`
Opening slide.

Front matter: `title`, `subtitle?`, `authors?`, `venue?`, `date?`.
Body: ignored (put info in front matter).

### `section`
Section divider.

Front matter: `title`, `subtitle?`.
Body: optional short statement; rendered as a large caption.

### `bullets`
Title + single bullet list, the workhorse layout.

Front matter: `title`, `subtitle?`.
Body: a markdown bullet list. Sub-bullets allowed (one level).

### `two-column`
Title + two side-by-side columns.

Front matter: `title`, `subtitle?`.
Body: two columns separated by a line containing exactly `::column`. Each column can have its own heading and bullets.

```markdown
---
layout: two-column
title: Motivation
---

## The Bottleneck
- classical verifiers need hand-written specs
- weeks per kLoC

::column

## Our Bet
- LLM writes the specs
- compositional Hoare-style reasoning
```

### `image-right` / `image-left`
Title + text on one side, image on the other.

Front matter: `title`, `image: path/to/file.png`, `caption?`, `subtitle?`.
Body: text / bullets (goes on the side opposite the image).

### `stat-row`
One title + a row of 2-4 large number+label pairs.

Front matter: `title`, `subtitle?`.
Body: a bullet list where each bullet is `<number> | <label>` (pipe-separated).

```markdown
---
layout: stat-row
title: Case Study
---

- 143K | lines of C
- 10+  | languages supported
- 5    | orchestrated stages
```

### `canvas`
Free-form. The agent composes the slide from inline components.

Front matter: `title?`, `subtitle?`, plus any prose that describes intent.
Body: a mix of markdown prose (intent + content) and inline component references.

Use `canvas` when the slide is a diagram, a flow, a non-standard arrangement — anything that doesn't fit a named layout.

---

## Inline components

Inside a slide body (most useful on `canvas`, but also allowed on other layouts), reference a component with:

```
::<component-name> <key>=<value> <key>="<value with spaces>" <key>=[v1, v2]
<optional multi-line body>
::end
```

### Rules

- The `::name` line is the opening tag. Arguments are `key=value` pairs, space-separated. Values that contain spaces use double quotes; lists use `[a, b, c]`.
- If the component has body content, it spans until `::end` (on its own line). If there's no body, omit `::end` — the component is a single line.
- One component per line — don't put `::component ...` inline with prose.
- Nesting allowed one level deep for container components (like `::column`, `::flow`).

### What the build agent does with them

The agent looks up each component in `components/_manifest.json` to find its params. Params you pass through in markdown (`title`, `body`, `variant`) become arguments to the component function. Params you omit — especially geometric ones like `x`, `y`, `w`, `h` — the agent decides based on slide layout and surrounding context.

### Example

```markdown
---
layout: canvas
title: System Pipeline
subtitle: Five orchestrated stages
---

Show the five pipeline stages left-to-right, each as a numbered circle
with a callout describing the stage, connected by arrows.

::step n=1 title="Decompose" body="Phases & modules"
::step n=2 title="Extract" body="Functions + call graph"
::step n=3 title="Layer" body="Topological ordering"
::step n=4 title="Specify" body="Top-down spec generation"
::step n=5 title="Verify" body="Hoare-style + probe"

Bottom row, left: input is a source codebase.
Bottom row, right: output is a set of confirmed bug reports.
```

Note how the *layout intent* ("left-to-right", "connected by arrows", "bottom row left/right") is in prose, and the *content and semantic component* is in `::step`. The agent resolves layout; the author resolves intent.

---

## Images

Three ways to include an image:

1. **As a layout param** — for `image-left` / `image-right` (above).
2. **Inline** — standard markdown image syntax: `![alt](path)`.
3. **Image stub** — a placeholder for an image that doesn't exist yet.

Paths are relative to the project root. Absolute paths also allowed.

### Image stubs

During authoring you often know *what* image a slide needs before you
have the actual file. Use an image stub to reserve space and capture
the intent, so the build doesn't block on missing assets and future
you doesn't forget what was supposed to go there.

**As a layout param** — set `image: STUB` (literal uppercase sentinel):

```markdown
---
layout: image-right
image: STUB
image_description: |
  A horizontal flow diagram showing the compilation pipeline:
  Lexer → Parser → AST → IR → CodeGen, each as a rounded box
  connected by arrows. Schematic style, not photorealistic.
caption: Pipeline overview
---

- bullets on the opposite side as usual
```

**As an inline component** (preferred on `canvas` slides):

```markdown
::image-stub caption="Pipeline overview"
A horizontal flow diagram showing the compilation pipeline:
Lexer → Parser → AST → IR → CodeGen, each as a rounded box
connected by arrows.
::end
```

The description body can span multiple lines. The build agent:

- Renders a dashed-outline placeholder at the computed position.
- Shows the caption inside the box for at-a-glance clarity.
- **Appends the full description to the slide's speaker notes**
  (PowerPoint presenter view), prefixed with `[IMAGE STUB]` and the
  stub's caption, so the description survives into the .pptx.

When you later produce the real image, replace the stub with a normal
`image:` front-matter entry or `![](path)` inline reference.

---

## What NOT to put in markdown

- ❌ Hex colors or palette names (`color: blue`, `color: #FF0000`)
- ❌ Coordinates (`x=0.6 y=2.0`) — let the build agent decide, unless the slide is genuinely a coordinate-driven diagram and you want to lock placement
- ❌ Font sizes or faces
- ❌ Any pptxgenjs keyword (`addText`, `addShape`, …)

If you find yourself writing any of the above, either the markdown schema is missing an expressive primitive (raise it with the user), or the work belongs in `theme.json` / a component definition.

---

## Comments

Lines starting with `%%` are treated as author notes — they do not appear in the output deck. Use them for "todo" markers or for speaker notes that shouldn't render.

```markdown
---
layout: bullets
title: Evaluation
---

- 143K-LoC case study on Claude's C Compiler
- 10+ languages supported
%% TODO: add the benchmark table once numbers are final
- Bugs reported with reproducible probes
```

For actual PowerPoint speaker notes (visible in presenter view), use a `notes:` key in the slide's front matter:

```markdown
---
layout: bullets
title: Case Study
notes: |
  Spend 2 minutes on this slide. Emphasize the scale
  argument over the correctness argument.
---
```

---

## Minimum valid deck

```markdown
---
layout: title
title: Hello
authors: Me
---

---
layout: bullets
title: One slide
---

- first point
- second point
```

Two slides. No styling mentioned. No coordinates. The build agent fills in everything else from the project's theme, components, and CLAUDE.md.
