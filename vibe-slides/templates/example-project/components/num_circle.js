// num_circle — the skill's recurring motif: a solid circle with a number inside.
//
// Use for: numbered steps, section markers, flow diagrams.
//
// props:
//   x, y      top-left of the circle (inches)
//   d         diameter in inches     default 0.6
//   n         the number (or any short text) to display
//   color     background hex         default theme.color.primary
//   textColor text hex               default theme.color.onPrimary

function num_circle(slide, props, pres, theme) {
  const { x, y, d = 0.6, n, color, textColor } = props;
  const fill = color || theme.color.primary;
  const txt  = textColor || theme.color.onPrimary;

  slide.addShape(pres.shapes.OVAL, {
    x, y, w: d, h: d,
    fill: { color: fill },
    line: { color: fill, width: 0 },
  });
  slide.addText(String(n), {
    x, y, w: d, h: d,
    fontFace: theme.font.head,
    fontSize: Math.round(d * 30),      // scale with diameter
    bold: true,
    color: txt,
    align: "center",
    valign: "middle",
    margin: 0,
  });
}

module.exports = num_circle;
