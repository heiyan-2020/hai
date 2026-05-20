// arrow — directed arrow between two points.
//
// Use for: flow diagrams, connecting callouts, indicating sequence.
//
// props:
//   from   [x, y] start point (inches)
//   to     [x, y] end point
//   style  "solid" | "dashed"     default "solid"
//   width  line thickness in pt   default 1.5
//   color  hex (no "#")           default theme.color.accent

function arrow(slide, props, pres, theme) {
  const { from, to, style = "solid", width = 1.5, color } = props;
  if (!Array.isArray(from) || !Array.isArray(to)) {
    throw new Error("arrow: 'from' and 'to' must be [x, y] pairs");
  }
  const lineColor = color || theme.color.accent;
  const [x1, y1] = from;
  const [x2, y2] = to;

  slide.addShape(pres.shapes.LINE, {
    x: Math.min(x1, x2),
    y: Math.min(y1, y2),
    w: Math.abs(x2 - x1),
    h: Math.abs(y2 - y1),
    flipH: x2 < x1,
    flipV: y2 < y1,
    line: {
      color: lineColor,
      width,
      dashType: style === "dashed" ? "dash" : "solid",
      endArrowType: "triangle",
    },
  });
}

module.exports = arrow;
