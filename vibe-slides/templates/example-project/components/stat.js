// stat — large-number callout with a small label beneath.
//
// Use for: headline metrics, stat rows (e.g., "143K lines of code").
//
// props:
//   x, y, w, h  required geometry
//   number      the big number/text (e.g., "143K", "10+", "5")
//   label       the small descriptive label
//   accent      hex color (no "#") for the top bar and the number;
//               defaults to theme.color.accent

function stat(slide, props, pres, theme) {
  const { x, y, w, h, number, label, accent } = props;
  const color = accent || theme.color.accent;

  // Surface
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y, w, h,
    fill: { color: theme.color.surface },
    line: { color: theme.color.border, width: 1 },
    shadow: { type: "outer", color: "000000", blur: 10, offset: 2, angle: 135, opacity: 0.06 },
  });

  // Top accent bar
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y, w, h: 0.12,
    fill: { color },
    line: { color, width: 0 },
  });

  // Big number
  slide.addText(String(number), {
    x, y: y + 0.35,
    w, h: h * 0.55,
    fontFace: theme.font.head,
    fontSize: theme.size.statBig,
    bold: true,
    color,
    align: "center",
    valign: "middle",
    margin: 0,
  });

  // Label
  slide.addText(label, {
    x, y: y + h * 0.72,
    w, h: h * 0.25,
    fontFace: theme.font.body,
    fontSize: theme.size.caption + 1,
    italic: true,
    color: theme.color.muted,
    align: "center",
    margin: 0,
  });
}

module.exports = stat;
