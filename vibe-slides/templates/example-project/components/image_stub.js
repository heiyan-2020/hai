// image_stub — placeholder for an image that doesn't exist yet.
//
// Renders a dashed-outline rectangle with a "[ image stub ]" label and
// an optional caption. The build agent is expected to ALSO append the
// full description to the slide's speaker notes (see build-slides.md).
//
// Use during authoring, before the real image asset is made. Replace
// with the real image later by swapping ::image-stub → a real image
// reference.
//
// props:
//   x, y, w, h   required geometry
//   caption      optional short caption shown at bottom inside the box
//   description  optional multi-line description shown centered in box
//                (agent should also put this in slide.addNotes)

function image_stub(slide, props, pres, theme) {
  const { x, y, w, h, caption, description } = props;

  // Outer dashed rectangle — clearly communicates "not final"
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y, w, h,
    fill: { color: theme.color.secondary || "F0F0F0" },
    line: { color: theme.color.muted, width: 1.5, dashType: "dash" },
  });

  // Top label strip
  slide.addText("[ image stub ]", {
    x, y: y + 0.15, w, h: 0.35,
    fontFace: theme.font.body,
    fontSize: theme.size.caption,
    italic: true,
    color: theme.color.muted,
    align: "center",
    charSpacing: 3,
    margin: 0,
  });

  // Middle: short description (first ~200 chars max to keep it readable)
  if (description) {
    const short = description.length > 200
      ? description.slice(0, 197).trim() + "…"
      : description;
    slide.addText(short, {
      x: x + 0.4,
      y: y + 0.55,
      w: w - 0.8,
      h: h - (caption ? 1.1 : 0.7),
      fontFace: theme.font.body,
      fontSize: theme.size.small,
      color: theme.color.muted,
      align: "center",
      valign: "middle",
      margin: 0,
    });
  }

  // Bottom caption (shown on the slide itself, not just in notes)
  if (caption) {
    slide.addText(caption, {
      x, y: y + h - 0.45, w, h: 0.35,
      fontFace: theme.font.body,
      fontSize: theme.size.small,
      bold: true,
      color: theme.color.text,
      align: "center",
      margin: 0,
    });
  }
}

module.exports = image_stub;
