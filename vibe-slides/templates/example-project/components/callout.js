// callout — card with a colored left accent bar.
//
// Use for: side notes, emphasized claims, labeled blocks.
//
// props:
//   x, y, w, h  required geometry (inches)
//   title       optional bold header inside the card
//   body        main text (rich-text array or plain string)
//   variant     "info" | "warn" | "ok" | "muted"  → picks the accent color
//
// The card uses theme.color.surface as fill, theme.color.border for outline,
// and the variant-selected color for the left accent bar.

function callout(slide, props, pres, theme) {
  const { x, y, w, h, title, body, variant = "info" } = props;

  const accent = {
    info:  theme.color.primary,
    warn:  theme.color.coral,
    ok:    theme.color.teal,
    muted: theme.color.muted,
  }[variant] || theme.color.primary;

  // Main surface
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y, w, h,
    fill: { color: theme.color.surface },
    line: { color: theme.color.border, width: 1 },
    shadow: { type: "outer", color: "000000", blur: 8, offset: 2, angle: 135, opacity: 0.06 },
  });

  // Left accent bar
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y, w: 0.1, h,
    fill: { color: accent },
    line: { color: accent, width: 0 },
  });

  const padX = 0.25;
  const textX = x + 0.1 + padX;
  const textW = w - 0.1 - padX * 2;

  if (title) {
    slide.addText(title, {
      x: textX, y: y + 0.12,
      w: textW, h: 0.4,
      fontFace: theme.font.head,
      fontSize: theme.size.h3,
      bold: true,
      color: theme.color.text,
      margin: 0,
    });
    slide.addText(body, {
      x: textX, y: y + 0.52,
      w: textW, h: h - 0.6,
      fontFace: theme.font.body,
      fontSize: theme.size.body,
      color: theme.color.text,
      margin: 0,
      valign: "top",
    });
  } else {
    slide.addText(body, {
      x: textX, y: y + 0.15,
      w: textW, h: h - 0.3,
      fontFace: theme.font.body,
      fontSize: theme.size.body,
      color: theme.color.text,
      margin: 0,
      valign: "middle",
    });
  }
}

module.exports = callout;
