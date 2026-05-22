---
description: "Extract reusable visual components from a .pptx into the project's components/ directory. (Currently a stub — bootstraps from the example project.)"
argument-hint: <demo.pptx>
---

# /vibe-slides:component-extractor &lt;demo.pptx&gt;

Extract reusable visual components from a .pptx into the project's
`components/` directory.

**Status: STUB — not yet implemented in round 1 of the skill.**

For now, bootstrap components by copying from the example project. Resolve
`<PLUGIN_ROOT>` as the root of this installed plugin. In Claude Code, this
command usually finds it:

```bash
ls -d ~/.claude/plugins/cache/*/vibe-slides/*/ 2>/dev/null | sort -V | tail -1
```

Substitute the absolute path for `<PLUGIN_ROOT>`, then:

```bash
cp -r <PLUGIN_ROOT>/templates/example-project/components \
      <your-project>/components
```

Available out-of-the-box: `callout`, `arrow`, `stat`, `num_circle`. You
can add more by hand following the component contract (see below).

## Component contract

Every `components/<name>.js` exports a single function:

```javascript
function componentName(slide, props, pres, theme) {
  // read props (e.g. props.x, props.title, props.variant)
  // read theme.color.*, theme.font.*, theme.size.*
  // call slide.addShape(...) / slide.addText(...) / slide.addImage(...)
}
module.exports = componentName;
```

And the project's `components/_manifest.json` registers it:

```json
{
  "version": 1,
  "components": {
    "<name>": {
      "file": "<name>.js",
      "summary": "one-line purpose",
      "params": {
        "x": { "type": "number", "required": true },
        ...
      },
      "preview": "previews/<name>.png"
    }
  }
}
```

Follow these conventions when adding by hand:

- Geometry always in inches.
- Variant colors picked by mapping a `variant` enum to theme color keys;
  never hardcode hex.
- `props` is always a single object; no positional args beyond
  `(slide, props, pres, theme)`.
- If the component supports semantic modes, expose them as a
  `variant` enum, not as separate components.

## When this is implemented

The script will live at `lib/extract_components.py` and will:

1. Read the input .pptx with `python-pptx`.
2. For each slide, enumerate shapes and suggest:
   - "decorative" shapes (usually a background or accent rectangle)
   - "parameter" shapes (short text frames that likely map to slots)
3. Present each slide's inferred component to the user and ask which
   text frames should become parameters (`title`, `body`, …) and which
   stay fixed.
4. Generate `<name>.js` from the component template, baking the
   decorative shapes as literals and turning parameter shapes into
   props.
5. Update `_manifest.json`.
6. Render a preview PNG per component (requires soffice + pdftoppm).
