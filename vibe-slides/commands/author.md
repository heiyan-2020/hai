---
description: "Collaborate with the user to write or iterate on slides.md (the content phase — style is deliberately out of scope)."
---

# /vibe-slides:author

Collaborate with the user to write or iterate on `slides.md` in their
project directory. This is the content phase — **style is deliberately
out of scope**.

---

## Before you start

Read in this order:

1. The project's `vibe-slides.md` (for tone, audience, any deck-specific
   constraints — skim; don't yet apply style).
2. `components/_manifest.json` — to know which symbolic components the
   markdown can reference.
3. [`schema/markdown-schema.md`](../schema/markdown-schema.md) (this plugin) —
   the grammar you're writing in.
4. The existing `slides.md` if there is one.

---

## Mode of interaction

You're a **thinking partner**, not a transcriber:

- Ask what the talk is about, who the audience is, how long it should be.
- Propose a slide outline (just titles + one-line purpose each) before
  writing any slide in full. Get user buy-in on the outline.
- Write slides one section at a time; pause for feedback, don't dump
  the whole deck.
- When you hear a structural idea, sketch it in markdown and show the
  diff, don't just commit silently.
- Probe weak slides: is this slide really needed? Can two be merged?
  Does the argument flow work?

## What to write in `slides.md`

Everything the markdown schema allows, and nothing more:

- ✅ Slide `layout`s from the schema's catalog
- ✅ Titles, subtitles, prose, bullets
- ✅ Symbolic component references (`::callout variant=info title="..."`)
- ✅ Image paths (`![](figures/foo.png)` or `image:` in front matter)
- ✅ Prose intent on `canvas` slides ("show the five stages
  left-to-right, connected by arrows")
- ✅ `%%` comments for TODOs or private notes
- ✅ `notes:` in front matter for speaker notes

## What to NOT write in `slides.md`

- ❌ Colors, hex codes, or palette names
- ❌ Font names or font sizes
- ❌ Coordinates — unless the user has explicitly asked to pin a
  diagram's geometry
- ❌ pptxgenjs code — the build agent writes that
- ❌ Layout hacks like raw HTML or tables-to-force-alignment

If a user asks for something that would require the above, push back:
"That's a style decision — let's keep it out of the markdown and handle
it during build, or add it to the theme/vibe-slides.md."

---

## Component selection

When the user describes a visual:

- **"Big number with a caption"** → `::stat`
- **"Labeled callout box"** → `::callout`
- **"Arrow from X to Y"** → `::arrow`
- **"Numbered step"** → `::num_circle` (+ usually a `::callout` next to it)
- **A diagram / photo / chart the user doesn't have a file for yet**
  → `::image-stub` (inline) or `image: STUB` + `image_description:` in
  front matter. Capture the intended content and style in the
  description — it survives into the .pptx speaker notes so nobody
  forgets what the slot is for. When the real image is produced,
  swap the stub for `image: <path>` or `![](path)`.
- **Something the library doesn't cover** → note it as a TODO comment
  (`%% need: timeline component`) and proceed with prose on a canvas
  slide for now. Don't invent components from the authoring side —
  the user adds them via `/vibe-slides component-extractor`.

**Proactively offer stubs.** If the user describes a visual but doesn't
mention a file path, ask: "Do you already have the image file, or
should I mark it as a stub with a description?" Stubs are the default
during authoring.

Always look up parameter names in `components/_manifest.json` — never
guess. If a component's `params` mention geometric fields (x, y, w, h),
**leave them out of the markdown** unless the user wants to pin position.
The build agent decides geometry.

---

## Iterating

Common operations during the session:

- **Add a slide**: insert after the relevant `---` separator.
- **Reorder**: ask the user whether they want to see the new order
  before committing; a reorder changes the story.
- **Split a slide**: when a slide has two distinct points, suggest
  splitting rather than cramming.
- **Merge slides**: when two adjacent slides restate the same point, offer
  to merge.
- **Convert layouts**: `bullets` → `two-column` is common when a list grows
  past ~5 items. Offer, don't impose.

Use the `Edit` tool to modify `slides.md`; don't rewrite the whole file
unless the user asks for a total restructure.

---

## What "done" looks like for this phase

You've reached the end of authoring when:

1. The user has confirmed the slide order.
2. Every slide has a clear purpose (one-line "what this slide proves").
3. No placeholder `%%` TODOs remain, or the remaining ones are
   explicitly marked as follow-ups.
4. Every component reference resolves against `_manifest.json`.
5. The user says "let's build."

Then suggest: "Run `/vibe-slides build` when ready."

---

## What NOT to do in authoring mode

- Don't run `node`, don't write `build.js`, don't produce a .pptx.
  Authoring and building are separate phases by design.
- Don't extract themes or components — those are their own commands.
- Don't touch `theme.json` or `components/` — those are owned by the
  extractor commands and by the user.
- Don't second-guess the style defaults. If the user complains the deck
  is "too boring," the fix is in vibe-slides.md (add motifs, tune theme), not
  in the markdown.
