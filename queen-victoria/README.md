# The Queen Victoria — Website

A complete, production-style website for **The Queen Victoria**, a British dining
house & bar in Wan Chai, Hong Kong. Full-stack: a luxury animated front end, a
real reservation engine with a SQLite backend, a live menu API, contact &
newsletter capture, an **AI concierge** powered by Claude, and SEO baked in.

> Everything is in English, fully self-contained (no external image
> dependencies), and runs with a single `npm start`.

---

## Highlights

- **Luxury front end** — Victorian heritage design (deep green, gold leaf, aged
  cream, ornate serifs), scroll-reveal & parallax animation, animated counters,
  a live "open now" indicator, and a custom procedurally-generated SVG art set.
- **Reservation system** — live availability by slot, capacity enforcement,
  instant confirmation references, large-party handling, and self-service
  lookup/cancel. Persisted in SQLite.
- **AI Concierge** — a streaming chat widget grounded in the restaurant's real
  data. Uses **Claude (`claude-opus-4-8`)** when an API key is set, with a
  deterministic knowledge-base fallback so it always works.
- **Live menu** — served from a JSON API with category and dietary filtering.
- **Contact & private-events** enquiry capture + newsletter sign-up.
- **SEO** — per-page meta & Open Graph, JSON-LD structured data (`BarOrPub`,
  `Menu`, `Event`), dynamic `sitemap.xml` and `robots.txt`, semantic markup,
  accessibility (skip links, ARIA, reduced-motion support).
- **Security & rate limiting** — Helmet CSP, CORS, compression, request-size
  limits, and tiered rate limiters (general / write / chat).

---

## Quick start

```bash
cd queen-victoria
npm install
cp .env.example .env        # optional — site runs without it
npm start                   # http://localhost:3000
```

Open <http://localhost:3000>. The concierge works immediately in local
knowledge-base mode. To enable the Claude-powered AI concierge, set
`ANTHROPIC_API_KEY` in `.env` and restart.

### Regenerate the artwork

```bash
node scripts/generate-assets.mjs
```

---

## Architecture

```
queen-victoria/
├── server/
│   ├── index.js              # Express app: security, SEO, static, routing
│   ├── db.js                 # SQLite schema + prepared statements
│   ├── data/
│   │   ├── restaurant.js     # single source of truth (hours, FAQ, policy…)
│   │   └── menu.js           # full menu
│   ├── middleware/
│   │   ├── rateLimit.js      # tiered limiters
│   │   └── validate.js       # input validation
│   └── routes/
│       ├── reservations.js   # availability + booking engine
│       ├── menu.js           # menu API (+ filters)
│       ├── contact.js        # enquiries + newsletter
│       └── chat.js           # AI concierge (Claude + fallback, SSE)
├── public/                   # front end (7 pages + 404)
│   ├── css/styles.css
│   ├── js/                   # main, concierge, reservations, menu, contact
│   └── assets/               # generated SVG art + crest/favicon
├── scripts/generate-assets.mjs
└── .env.example
```

## API reference

| Method | Endpoint | Description |
|---|---|---|
| `GET`  | `/api/health` | Service health |
| `GET`  | `/api/info` | Public venue info |
| `GET`  | `/api/menu?tag=&category=` | Menu, optionally filtered |
| `GET`  | `/api/reservations/availability?date=&party=` | Slot availability |
| `POST` | `/api/reservations` | Create a booking |
| `GET`  | `/api/reservations/:reference` | Look up a booking |
| `POST` | `/api/reservations/:reference/cancel` | Cancel a booking |
| `POST` | `/api/contact` | Enquiry / private event / feedback |
| `POST` | `/api/contact/newsletter` | Newsletter sign-up |
| `POST` | `/api/chat` | AI concierge (Server-Sent Events stream) |
| `GET`  | `/sitemap.xml`, `/robots.txt`, `/structured-data.json` | SEO |

## Configuration

See `.env.example`. All values are optional for local development.

| Variable | Purpose |
|---|---|
| `PORT` | Server port (default 3000) |
| `SITE_URL` | Canonical URL for SEO output |
| `ANTHROPIC_API_KEY` | Enables the Claude-powered concierge |
| `ANTHROPIC_MODEL` | Model override (default `claude-opus-4-8`) |
| `CORS_ORIGIN` | Restrict CORS in production |
| `DB_PATH` | SQLite file location |

## Notes

- The reservation `SLOT_CAPACITY` is a sensible default; tune it in
  `server/routes/reservations.js` to your real covers.
- Imagery is generated SVG so the site is beautiful offline. Drop in real
  photography by replacing the files in `public/assets/` (the CSP already
  allows `images.unsplash.com`).
