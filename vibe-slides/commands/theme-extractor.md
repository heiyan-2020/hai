---
description: "Extract theme tokens (colors, fonts, sizes, spacing, motifs) from a .pptx template into the project's theme.json."
argument-hint: <template.pptx>
---

# /vibe-slides:theme-extractor &lt;template.pptx&gt;

Extract theme tokens (colors, fonts, sizes, spacing, motifs) from a .pptx
template into the project's `theme.json`.

Two stages:

1. A Python script (`lib/extract_theme.py`) does the **mechanical
   extraction** — exhaustive dump of everything readable.
2. You (the agent) resolve **judgment calls** with the user, then write
   `theme.json`.

Never skip stage 2. The script deliberately leaves ambiguities for you.

---

## Resolving plugin paths

The shell snippets below reference this plugin's `lib/` and `templates/`.
Resolve `<PLUGIN_ROOT>` as the root of this installed plugin. In Claude Code,
this command usually finds it:

```bash
ls -d ~/.claude/plugins/cache/*/vibe-slides/*/ 2>/dev/null | sort -V | tail -1
```

In Codex, resolve it from the installed skill/plugin path. Substitute the
absolute path for `<PLUGIN_ROOT>` in every command below.

---

## Step 1 — Run the extractor

Working directory: the project root (where `theme.json` will live).

```bash
python3 <PLUGIN_ROOT>/lib/extract_theme.py \
    --input <path/to/template.pptx> \
    --output-dir .
```

This produces **two** files in the project:

- `theme.raw.json` — exhaustive dump: colors, declared fonts, observed
  fonts, every layout's placeholders + decorative shapes + declared
  font sizes.
- `extraction_report.md` — human-readable report with 5 sections of
  judgment calls.

If the script fails (missing `python-pptx`, malformed .pptx, etc.),
install the dep and retry. Do NOT hand-edit `theme.raw.json`.

---

## Step 2 — Read the report

Read `extraction_report.md` end-to-end before talking to the user.
It has five sections:

1. **Font — declared vs. observed.** The theme XML names one font; the
   author may have typed another at slide level. Mismatch is common
   and the user must choose.
2. **Motif candidates.** Any non-placeholder shape with a fill, especially
   ones that bleed off the edge.
3. **Color semantics.** The script proposes `primary`/`accent`/`text`/…
   mappings from the raw palette; user must confirm or re-map.
4. **Font size hierarchy.** All `sz` values found, mapped largest→smallest
   to `title`/`section`/`h3`/`body`/`small`/`caption`.
5. **Spacing from layout geometry.** `margin`, `titleY`, `titleH`
   inferred from the primary content layout's title placeholder.

---

## Step 3 — Resolve with the user

**Ask ONE focused question at a time.** Do not batch all 5 sections.

### Font

If declared = observed → tell the user what the font is, confirm, move on.

If mismatch → explain the conflict and recommend **what was actually
typed** (not what was declared). Wait for the user.

Example:
> The template declares Arial in its theme XML, but all 474 text runs
> across 40 slides use **Century Gothic** — the author overrode it at
> every slide. I recommend we commit to Century Gothic. OK?

### Motif

For each visually cohesive cluster in the report, describe what it looks
like (never just list coordinates) and ask:

> Layout `标题和内容` has two shapes at the left edge — a small vertical
> rectangle (0.24×0.63″) plus a right-pointing triangle, both filled with
> accent1 and bleeding slightly off the slide. Looks like a "bookmark
> flag." Promote to `theme.motif.bookmark = true` and render it via
> `addSlideTitle` on content slides?

If multiple clusters, ask separately. Don't assume they're the same motif.

### Colors

Describe the palette in one sentence before asking:

> Palette is a **warm single-accent theme** — deep red (`accent1`) as the
> signature color, supporting slate-gray and sand tones. The script
> suggests `primary` = `accent` = `#BE384B` (same hex for both roles since
> the template uses accent1 for titles AND decorations). Keep them unified,
> or split? (Splitting is rarely needed.)

Ask user whether to accept the recommended `text`, `muted`, `bg`, etc.
Trust the recommendation unless they push back.

### Font sizes

Present the proposed mapping compact:

> Declared sizes (pt): 48, 34.67, 32, 26.66, 24, 16. I'll map them as:
> title=48, section=34.67, h3=32, body=26.66 (round to 27), small=24,
> caption=16. OK?

Round fractional sizes (26.66 → 27) unless the user objects.

### Spacing

> Title placeholder in the content layout is at (0.67, 0.30, 12.00×1.08) in.
> I'll set `margin=0.67`, `titleY=0.30`, `titleH=1.08`. OK?

---

## Step 4 — Write `theme.json`

Once every section is resolved, synthesize one clean JSON:

```json
{
  "_source": "extracted from <input.pptx> via theme-extractor",
  "slide":  { "w": 13.33, "h": 7.5 },
  "color":  { "primary": "...", "accent": "...", "text": "...",
              "muted": "...", "bg": "...", "surface": "...",
              "secondary": "...", "border": "...",
              "coral": "...", "teal": "...",
              "onPrimary": "FFFFFF", "onAccent": "FFFFFF",
              "onSurface": "...", "primaryDeep": "..." },
  "font":   { "head": "...", "body": "...", "mono": "Consolas" },
  "size":   { "title": 32, "subtitle": 18, "section": 24, "h3": 20,
              "body": 16, "small": 14, "caption": 12, "statBig": 56 },
  "space":  { "margin": 0.67, "titleY": 0.30, "titleH": 1.08, "gap": 0.3 },
  "motif":  { "bookmark": true, "leftAccentBar": false, "footerRow": true,
              "numberedCircles": true }
}
```

Rules:

- **Every hex in `theme.json` must exist in `theme.raw.json`.** No
  inventing colors.
- **Leave fields empty if the user didn't decide.** Missing fields fall
  back to component defaults at build time. Incomplete is fine.
- **Preserve `_source`** — names the script run, for reproducibility.
- **Leave `statBig` = 56 and `onPrimary` / `onAccent` = white** unless
  the palette contradicts (e.g., yellow accent needs black onAccent).
- **`primaryDeep`** is a darker variant of `primary`, used for dark
  backgrounds on title/conclusion slides. You can compute it by
  multiplying each RGB channel by ~0.7, or ask the user.

---

## Step 5 — Clean up

After `theme.json` is written and confirmed:

```bash
rm <project>/theme.raw.json
rm <project>/extraction_report.md
```

Keep them only if the user explicitly asks to retain (e.g., for debugging).

---

## Smoke test

After writing `theme.json`, if the project already has `slides.md` and
`components/`, offer to run `/vibe-slides:build-slides` and view the
result. If not, tell the user theme extraction is done and explain next
steps:

1. Bootstrap components:
   `cp -r <PLUGIN_ROOT>/templates/example-project/components <project>/`
2. Bootstrap the project vibe-slides.md:
   `cp <PLUGIN_ROOT>/templates/vibe-slides.md.tmpl <project>/vibe-slides.md`
3. Write `slides.md` (via `/vibe-slides:author`).
4. Build (`/vibe-slides:build-slides`).
