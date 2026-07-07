# GBA CONSULTING × ANITA KO

> *Navigating the Nexus of Global Capital.*
> *領航全球資本，對接大灣區機遇。*
> *领航全球资本，对接大湾区机遇。*

The definitive digital experience for **GBA Consulting / GBA Partners**, led by **Anita Ko** — a cinematic, bilingual WebGL site bridging Hong Kong finance and the Greater Bay Area tech ecosystem.

## Quick Start

```bash
npm install
npm run dev        # local dev at http://localhost:5173
npm run build      # single-file production build → dist/index.html
npm run preview    # serve the production build
```

## Deploy to Netlify (one file)

The build is configured with `vite-plugin-singlefile`, so `npm run build` produces **one self-contained `dist/index.html`** (all JS + CSS inlined; only the Google Fonts request is external). A ready-made copy is committed at [`deploy/index.html`](deploy/index.html).

Drag the `deploy/` folder onto [Netlify Drop](https://app.netlify.com/drop) — done. (Any static host works the same way.)

## The Experience

- **The GBA Nexus hero** — a generative point-cloud constellation of the 11 GBA cities (GDP-weighted clusters, golden corridors between hubs), floating over a custom-GLSL **"digital silk" liquid-metal shader** that flows toward the cursor.
- **Interactive nodes** — hovering Hong Kong, Shenzhen or Guangzhou performs a **cinematic camera zoom** and reveals micro-data (GDP, tech output) in a glassmorphic card. All 11 cities respond.
- **Post-processing** — Bloom, Chromatic Aberration (flares during the zoom), film-grain Noise, Vignette, and **Depth of Field that shifts with scroll**.
- **Preloader** — percentage counter, conic-sweep ring, staggered GBA monogram reveal.
- **The Anita Ko Philosophy** — signature section with GSAP-drawn flourish and scroll-triggered typography.
- **Three Pillars of Excellence** — Strategic Advisory / Partnership Network / Project Implementation, in glass cards with 3D tilt reveals.
- **The GBA Data Vault** — a second WebGL canvas: rotating 3D GDP columns for all 11 cities (hover for values), an odometer counting to **$1.67T**, and HK-standard finance terminology chips (跨境金融 · 合規諮詢).
- **Contact Portal** — a private member's-club application form with a wax-seal confirmation state.
- **Trilingual engine** — a magnetic EN / 繁 / 简 toggle; all strings live in a structured resource object (`src/i18n/translations.js`). The Traditional Chinese copy is written to Hong Kong business register (港式商務繁體) and the Mandarin copy to mainland business register (内地商务简体), not machine-translated.

## Stack

| Layer | Technology |
|---|---|
| Framework | React 18 + Vite |
| 3D | three.js + @react-three/fiber + drei |
| Post-processing | @react-three/postprocessing |
| Custom shaders | GLSL (digital-silk backdrop, breathing point cloud) |
| UI animation | Framer Motion (magnetic toggle uses spring physics) |
| Timelines | GSAP + ScrollTrigger |
| Scrolling | Lenis smooth scroll, synced to ScrollTrigger and the WebGL scene |
| Styling | Tailwind CSS + custom glassmorphism / neomorphism utilities |

## Structure

```
src/
├── i18n/            # LanguageContext + EN / 繁 resource object
├── data/cities.js   # 11 GBA cities: coordinates, GDP, tech output
├── three/           # WebGL: Scene, LiquidSilk shader, GBANexus, camera rig
├── components/      # Preloader, Navbar, Hero, Philosophy, Pillars,
│                    # DataVault (3D chart), Contact, Footer
└── hooks/useLenis.js
```

Responsive throughout — mobile keeps the full 3D nexus with a reduced particle budget and lighter post-processing.
