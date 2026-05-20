// Render helpers shared by every vibe-slides build.js.
//
// Stays in the plugin — never copied into the project. The build agent
// discovers the plugin install root and writes the absolute path into
// the generated build.js, e.g.:
//
//   const { createDeck, loadComponents, addFooter, addSlideTitle } =
//     require("/home/<you>/.claude/plugins/cache/<marketplace>/vibe-slides/<version>/lib/render_helpers.js");
//
// See commands/build-slides.md ("Resolving plugin paths") for the
// discovery snippet.
//
//   const { pres, theme, components } = createDeck("./");
//   const s = pres.addSlide();
//   s.background = { color: theme.color.bg };
//   addSlideTitle(s, theme, "Slide title", "Optional subtitle");
//   components.callout(s, { x: 0.7, y: 2.0, w: 5, h: 1.2,
//                           title: "Note", body: "something useful" });
//   addFooter(s, theme, 2, 12);
//   pres.writeFile({ fileName: "./out.pptx" });
//
// The helper enforces exactly two conventions:
//   - components receive (slide, props, pres, theme) in that order
//   - pres is configured from theme.slide dimensions

const fs   = require("fs");
const path = require("path");

function _resolvePptxgen() {
  // Prefer globally installed pptxgenjs so projects don't need a per-project
  // node_modules. We set NODE_PATH at call sites; require() walks it.
  return require("pptxgenjs");
}

function loadTheme(projectDir) {
  const themePath = path.join(projectDir, "theme.json");
  if (!fs.existsSync(themePath)) {
    throw new Error(`vibe-slides: theme.json not found at ${themePath}`);
  }
  return JSON.parse(fs.readFileSync(themePath, "utf8"));
}

function loadComponents(projectDir) {
  const dir = path.join(projectDir, "components");
  const manifestPath = path.join(dir, "_manifest.json");
  if (!fs.existsSync(manifestPath)) {
    throw new Error(`vibe-slides: components/_manifest.json not found`);
  }
  const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
  const components = {};
  for (const [name, spec] of Object.entries(manifest.components || {})) {
    const modPath = path.join(dir, spec.file);
    if (!fs.existsSync(modPath)) {
      throw new Error(`vibe-slides: component '${name}' declared in manifest but file missing: ${modPath}`);
    }
    components[name] = require(modPath);
  }
  return { components, manifest };
}

function createDeck(projectDir) {
  const pptxgen = _resolvePptxgen();
  const theme   = loadTheme(projectDir);
  const { components: rawComponents, manifest } = loadComponents(projectDir);

  const pres = new pptxgen();
  // Pick layout based on aspect ratio in theme. Default LAYOUT_WIDE (13.3 x 7.5).
  const w = theme.slide?.w ?? 13.33;
  const h = theme.slide?.h ?? 7.5;
  if (Math.abs(w - 13.33) < 0.01 && Math.abs(h - 7.5) < 0.01) {
    pres.layout = "LAYOUT_WIDE";
  } else if (Math.abs(w - 10) < 0.01 && Math.abs(h - 5.625) < 0.01) {
    pres.layout = "LAYOUT_16x9";
  } else {
    pres.defineLayout({ name: "CUSTOM", width: w, height: h });
    pres.layout = "CUSTOM";
  }

  // Wrap each raw component so call sites can do components.callout(slide, props)
  // without passing pres + theme every time.
  const components = {};
  for (const [name, fn] of Object.entries(rawComponents)) {
    components[name] = (slide, props) => fn(slide, props, pres, theme);
  }

  return { pres, theme, components, manifest, dims: { w, h } };
}

// ---- Common slide-level helpers ---------------------------------------------

function addSlideTitle(slide, theme, title, subtitle) {
  slide.addText(title, {
    x: theme.space.margin,
    y: theme.space.titleY ?? 0.35,
    w: (theme.slide?.w ?? 13.33) - 2 * theme.space.margin,
    h: theme.space.titleH ?? 0.7,
    fontFace: theme.font.head,
    fontSize: theme.size.title,
    bold: true,
    color: theme.color.primary,
    margin: 0,
  });
  if (subtitle) {
    slide.addText(subtitle, {
      x: theme.space.margin,
      y: (theme.space.titleY ?? 0.35) + (theme.space.titleH ?? 0.7) - 0.05,
      w: (theme.slide?.w ?? 13.33) - 2 * theme.space.margin,
      h: 0.4,
      fontFace: theme.font.body,
      fontSize: theme.size.subtitle,
      italic: true,
      color: theme.color.muted,
      margin: 0,
    });
  }
  // Motif: small accent bar beside the title, OR a bookmark-flag shape
  // bleeding off the slide's left edge. Exactly one (or neither) should be on.
  if (theme.motif?.leftAccentBar) {
    slide.addShape("rect", {
      x: theme.space.margin - 0.25,
      y: (theme.space.titleY ?? 0.35) + 0.13,
      w: 0.12,
      h: (theme.space.titleH ?? 0.7) - 0.3,
      fill: { color: theme.color.accent },
      line: { color: theme.color.accent, width: 0 },
    });
  }
  if (theme.motif?.bookmark) {
    // Vertical rect bleeding off the left edge
    slide.addShape("rect", {
      x: -0.26,
      y: (theme.space.titleY ?? 0.30) + 0.28,
      w: 0.24,
      h: 0.63,
      fill: { color: theme.color.accent },
      line: { color: theme.color.accent, width: 0 },
    });
    // Triangle pointing right, tucked right below the rect
    slide.addShape("rtTriangle", {
      x: -0.20,
      y: (theme.space.titleY ?? 0.30) + 0.48,
      w: 0.63,
      h: 0.23,
      rotate: 270,
      fill: { color: theme.color.accent },
      line: { color: theme.color.accent, width: 0 },
    });
  }
}

function addFooter(slide, theme, pageNum, total, opts = {}) {
  const w = theme.slide?.w ?? 13.33;
  const h = theme.slide?.h ?? 7.5;

  if (theme.motif?.footerRow) {
    // Template-style: date / footer-label / page-number row at y=6.95
    const y = h - 0.55;
    if (opts.date) {
      slide.addText(opts.date, {
        x: theme.space.margin, y, w: 3.1, h: 0.4,
        fontFace: theme.font.body, fontSize: theme.size.small,
        color: theme.color.muted, margin: 0,
      });
    }
    if (opts.label) {
      slide.addText(opts.label, {
        x: 4.56, y, w: 4.22, h: 0.4,
        fontFace: theme.font.body, fontSize: theme.size.small,
        color: theme.color.muted, align: "center", margin: 0,
      });
    }
    if (pageNum != null && total != null) {
      slide.addText(`${pageNum} / ${total}`, {
        x: w - 3.8, y, w: 3.1, h: 0.4,
        fontFace: theme.font.body, fontSize: theme.size.small,
        color: theme.color.muted, align: "right", margin: 0,
      });
    }
  } else {
    // Fallback: thin accent stripe + corner page number
    slide.addShape("rect", {
      x: 0, y: h - 0.08, w, h: 0.08,
      fill: { color: theme.color.accent },
      line: { color: theme.color.accent, width: 0 },
    });
    if (pageNum != null && total != null) {
      slide.addText(`${pageNum} / ${total}`, {
        x: w - 1.3, y: h - 0.48, w: 0.8, h: 0.3,
        fontFace: theme.font.body, fontSize: theme.size.caption,
        color: theme.color.muted, align: "right", margin: 0,
      });
    }
  }
}

module.exports = {
  createDeck,
  loadTheme,
  loadComponents,
  addSlideTitle,
  addFooter,
};
