/* Generates the site's atmospheric SVG artwork procedurally so the experience
   is rich and fully self-contained (no external image dependencies). Run with:
   `node scripts/generate-assets.mjs`. Re-run any time to regenerate. */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const out = path.join(__dirname, "..", "public", "assets");
fs.mkdirSync(out, { recursive: true });

// Tiny seeded PRNG for repeatable scenes.
function rng(seed) {
  let s = seed >>> 0;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
}

const PALETTES = {
  green:  { top: "#15402F", bot: "#081E18", glow: "#E2B85A" },
  amber:  { top: "#2A1E10", bot: "#10342A", glow: "#F0C56B" },
  wine:   { top: "#2A1119", bot: "#0A211B", glow: "#E8B86A" },
  night:  { top: "#0E2A22", bot: "#06140F", glow: "#D9C089" },
  copper: { top: "#241A12", bot: "#0B241D", glow: "#E8C07A" },
  sage:   { top: "#1C4A3C", bot: "#0A211B", glow: "#EAD79B" },
};

function scene(w, h, seed, paletteName, opts = {}) {
  const r = rng(seed);
  const p = PALETTES[paletteName] || PALETTES.green;
  const id = `s${seed}`;
  let svg = `<svg viewBox="0 0 ${w} ${h}" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid slice">`;
  svg += `<defs>
    <linearGradient id="bg${id}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="${p.top}"/><stop offset="1" stop-color="${p.bot}"/>
    </linearGradient>
    <radialGradient id="glow${id}" cx="50%" cy="28%" r="60%">
      <stop offset="0" stop-color="${p.glow}" stop-opacity="0.55"/>
      <stop offset="40%" stop-color="${p.glow}" stop-opacity="0.12"/>
      <stop offset="100%" stop-color="${p.glow}" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="vig${id}" cx="50%" cy="46%" r="75%">
      <stop offset="55%" stop-color="#000" stop-opacity="0"/>
      <stop offset="100%" stop-color="#000" stop-opacity="0.55"/>
    </radialGradient>
    <filter id="grain${id}"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" stitchTiles="stitch"/>
      <feColorMatrix type="saturate" values="0"/>
      <feComponentTransfer><feFuncA type="linear" slope="0.05"/></feComponentTransfer>
      <feComposite operator="over" in2="SourceGraphic"/></filter>
    <filter id="soft${id}"><feGaussianBlur stdDeviation="${opts.blur ?? 6}"/></filter>
  </defs>`;

  svg += `<rect width="${w}" height="${h}" fill="url(#bg${id})"/>`;
  svg += `<rect width="${w}" height="${h}" fill="url(#glow${id})"/>`;

  // Pendant lights across the top.
  const lights = opts.lights ?? 4;
  for (let i = 0; i < lights; i++) {
    const x = (w / (lights + 1)) * (i + 1) + (r() - 0.5) * 40;
    const y = h * (0.1 + r() * 0.08);
    svg += `<line x1="${x.toFixed(0)}" y1="0" x2="${x.toFixed(0)}" y2="${(y - 14).toFixed(0)}" stroke="${p.glow}" stroke-opacity="0.25" stroke-width="1"/>`;
    svg += `<circle cx="${x.toFixed(0)}" cy="${y.toFixed(0)}" r="${(26 + r() * 16).toFixed(0)}" fill="${p.glow}" opacity="0.18" filter="url(#soft${id})"/>`;
    svg += `<circle cx="${x.toFixed(0)}" cy="${y.toFixed(0)}" r="5" fill="${p.glow}" opacity="0.9"/>`;
  }

  // Bokeh.
  const dots = opts.dots ?? 26;
  for (let i = 0; i < dots; i++) {
    const x = r() * w, y = h * (0.15 + r() * 0.8), rad = 3 + r() * 22;
    svg += `<circle cx="${x.toFixed(0)}" cy="${y.toFixed(0)}" r="${rad.toFixed(0)}" fill="${p.glow}" opacity="${(0.04 + r() * 0.1).toFixed(2)}" filter="url(#soft${id})"/>`;
  }

  // Bottle / silhouette shelf at the base.
  if (opts.shelf !== false) {
    const shelfY = h * 0.66;
    svg += `<rect x="0" y="${shelfY.toFixed(0)}" width="${w}" height="${(h - shelfY).toFixed(0)}" fill="#000" opacity="0.32"/>`;
    let x = w * 0.04;
    while (x < w * 0.96) {
      const bw = 14 + r() * 16;
      const bh = 60 + r() * 90;
      const by = shelfY - bh + 10;
      svg += `<rect x="${x.toFixed(0)}" y="${by.toFixed(0)}" width="${bw.toFixed(0)}" height="${bh.toFixed(0)}" rx="${(bw / 2).toFixed(0)}" fill="#000" opacity="0.5"/>`;
      svg += `<rect x="${x.toFixed(0)}" y="${by.toFixed(0)}" width="2" height="${bh.toFixed(0)}" fill="${p.glow}" opacity="0.35"/>`;
      x += bw + 6 + r() * 18;
    }
  }

  svg += `<rect width="${w}" height="${h}" fill="url(#vig${id})"/>`;
  svg += `<rect width="${w}" height="${h}" filter="url(#grain${id})" opacity="0.5"/>`;
  svg += `</svg>`;
  return svg;
}

const jobs = [
  ["hero.svg", () => scene(1600, 1000, 101, "green", { lights: 5, dots: 34 })],
  ["page-menu.svg", () => scene(1600, 600, 202, "amber", { lights: 4 })],
  ["page-reserve.svg", () => scene(1600, 600, 303, "sage", { lights: 5 })],
  ["page-events.svg", () => scene(1600, 600, 404, "wine", { lights: 4 })],
  ["page-about.svg", () => scene(1600, 600, 505, "copper", { lights: 4 })],
  ["page-gallery.svg", () => scene(1600, 600, 606, "night", { lights: 6 })],
  ["page-contact.svg", () => scene(1600, 600, 707, "green", { lights: 4 })],
  ["interior.svg", () => scene(900, 1125, 808, "copper", { lights: 3, dots: 18 })],
  ["pour.svg", () => scene(900, 1125, 909, "amber", { lights: 2, dots: 16 })],
  // gallery tiles (varied heights / palettes)
  ["g1.svg", () => scene(800, 1000, 11, "green", { lights: 3 })],
  ["g2.svg", () => scene(800, 700, 22, "amber", { lights: 2 })],
  ["g3.svg", () => scene(800, 1100, 33, "wine", { lights: 3 })],
  ["g4.svg", () => scene(800, 800, 44, "copper", { lights: 2 })],
  ["g5.svg", () => scene(800, 950, 55, "night", { lights: 4 })],
  ["g6.svg", () => scene(800, 720, 66, "sage", { lights: 2 })],
];

for (const [name, fn] of jobs) {
  fs.writeFileSync(path.join(out, name), fn());
  console.log("wrote", name);
}

// Open Graph share image (1200x630) with crest + wordmark.
const og = `<svg viewBox="0 0 1200 630" xmlns="http://www.w3.org/2000/svg">
  ${scene(1200, 630, 999, "green", { lights: 5, dots: 30, shelf: true }).replace('<svg viewBox="0 0 1200 630" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid slice">', "").replace("</svg>", "")}
  <text x="600" y="300" text-anchor="middle" font-family="Playfair Display, Georgia, serif" font-size="84" font-weight="700" fill="#F7F2E7">The Queen Victoria</text>
  <text x="600" y="360" text-anchor="middle" font-family="Jost, sans-serif" font-size="26" letter-spacing="8" fill="#D9C089">A BRITISH DINING HOUSE &amp; BAR · WAN CHAI</text>
  <text x="600" y="430" text-anchor="middle" font-family="Cormorant Garamond, Georgia, serif" font-size="30" fill="#EFE7D4" opacity="0.9">Proper pub classics · Hand-pulled ales · The Gin Library</text>
</svg>`;
fs.writeFileSync(path.join(out, "og-image.svg"), og);
console.log("wrote og-image.svg");
