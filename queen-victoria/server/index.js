import "dotenv/config";
import express from "express";
import helmet from "helmet";
import cors from "cors";
import compression from "compression";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { restaurant } from "./data/restaurant.js";
import { apiLimiter } from "./middleware/rateLimit.js";
import reservationsRouter from "./routes/reservations.js";
import menuRouter from "./routes/menu.js";
import contactRouter from "./routes/contact.js";
import chatRouter from "./routes/chat.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const publicDir = path.join(__dirname, "..", "public");

const app = express();
const PORT = process.env.PORT || 3000;
const SITE_URL = (process.env.SITE_URL || `http://localhost:${PORT}`).replace(/\/$/, "");

app.set("trust proxy", 1);
app.disable("x-powered-by");

// --- Security & performance -------------------------------------------------
app.use(
  helmet({
    contentSecurityPolicy: {
      directives: {
        defaultSrc: ["'self'"],
        scriptSrc: ["'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net"],
        styleSrc: ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com", "https://cdn.jsdelivr.net"],
        fontSrc: ["'self'", "https://fonts.gstatic.com", "data:"],
        imgSrc: ["'self'", "data:", "https://images.unsplash.com", "https://*.tile.openstreetmap.org"],
        connectSrc: ["'self'"],
        frameSrc: ["'self'", "https://www.google.com", "https://maps.google.com"],
        objectSrc: ["'none'"],
        baseUri: ["'self'"],
        formAction: ["'self'"],
        upgradeInsecureRequests: process.env.NODE_ENV === "production" ? [] : null,
      },
    },
    crossOriginEmbedderPolicy: false,
  })
);
app.use(compression());
app.use(cors({ origin: process.env.CORS_ORIGIN || true }));
app.use(express.json({ limit: "64kb" }));
app.use(express.urlencoded({ extended: true, limit: "64kb" }));

// --- API --------------------------------------------------------------------
app.use("/api", apiLimiter);
app.use("/api/reservations", reservationsRouter);
app.use("/api/menu", menuRouter);
app.use("/api/contact", contactRouter);
app.use("/api/chat", chatRouter);

app.get("/api/health", (req, res) => res.json({ ok: true, service: "the-queen-victoria", time: new Date().toISOString() }));

// Public restaurant info (used by the front end & third parties).
app.get("/api/info", (req, res) => {
  res.json({
    ok: true,
    name: restaurant.name,
    tagline: restaurant.tagline,
    contact: restaurant.contact,
    address: restaurant.address,
    hours: restaurant.hours,
    hoursSummary: restaurant.hoursSummary,
    features: restaurant.features,
    highlights: restaurant.highlights,
    faq: restaurant.faq,
    ratings: restaurant.ratings,
  });
});

// --- SEO --------------------------------------------------------------------
const PAGES = [
  { loc: "/", priority: "1.0", changefreq: "weekly" },
  { loc: "/menu.html", priority: "0.9", changefreq: "weekly" },
  { loc: "/reservations.html", priority: "0.9", changefreq: "monthly" },
  { loc: "/events.html", priority: "0.8", changefreq: "weekly" },
  { loc: "/about.html", priority: "0.7", changefreq: "monthly" },
  { loc: "/gallery.html", priority: "0.6", changefreq: "monthly" },
  { loc: "/contact.html", priority: "0.7", changefreq: "monthly" },
];

app.get("/sitemap.xml", (req, res) => {
  const today = new Date().toISOString().slice(0, 10);
  const urls = PAGES.map(
    (p) =>
      `  <url><loc>${SITE_URL}${p.loc}</loc><lastmod>${today}</lastmod>` +
      `<changefreq>${p.changefreq}</changefreq><priority>${p.priority}</priority></url>`
  ).join("\n");
  res.type("application/xml").send(
    `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>`
  );
});

app.get("/robots.txt", (req, res) => {
  res.type("text/plain").send(`User-agent: *\nAllow: /\nDisallow: /api/\n\nSitemap: ${SITE_URL}/sitemap.xml\n`);
});

// JSON-LD structured data (Restaurant / Bar schema) for rich results.
app.get("/structured-data.json", (req, res) => {
  const r = restaurant;
  const dayMap = {
    Monday: "Monday", Tuesday: "Tuesday", Wednesday: "Wednesday",
    Thursday: "Thursday", Friday: "Friday", Saturday: "Saturday", Sunday: "Sunday",
  };
  res.json({
    "@context": "https://schema.org",
    "@type": "BarOrPub",
    name: r.name,
    description: r.description,
    image: `${SITE_URL}/assets/og-image.svg`,
    url: SITE_URL,
    telephone: r.contact.phone,
    email: r.contact.email,
    priceRange: r.priceRange,
    servesCuisine: r.cuisine,
    address: {
      "@type": "PostalAddress",
      streetAddress: `${r.address.line1}, ${r.address.line2}`,
      addressLocality: r.address.district,
      addressRegion: r.address.city,
      addressCountry: "HK",
    },
    geo: { "@type": "GeoCoordinates", latitude: r.geo.latitude, longitude: r.geo.longitude },
    aggregateRating: {
      "@type": "AggregateRating",
      ratingValue: r.ratings.average,
      reviewCount: r.ratings.count,
    },
    openingHoursSpecification: r.hours.map((h) => ({
      "@type": "OpeningHoursSpecification",
      dayOfWeek: dayMap[h.day],
      opens: h.open,
      closes: h.close === "00:00" ? "23:59" : h.close,
    })),
    acceptsReservations: `${SITE_URL}/reservations.html`,
    sameAs: [r.social.instagram, r.social.facebook],
  });
});

// --- Static site ------------------------------------------------------------
app.use(
  express.static(publicDir, {
    extensions: ["html"],
    setHeaders: (res, filePath) => {
      if (/\.(?:css|js|svg|png|jpg|webp|woff2?)$/.test(filePath)) {
        res.setHeader("Cache-Control", "public, max-age=86400");
      }
    },
  })
);

// 404 — API gets JSON, everything else gets the branded page.
app.use((req, res) => {
  if (req.path.startsWith("/api/")) return res.status(404).json({ ok: false, error: "Not found." });
  res.status(404).sendFile(path.join(publicDir, "404.html"));
});

// Error handler.
app.use((err, req, res, next) => {
  console.error("[server] error:", err?.message || err);
  if (res.headersSent) return next(err);
  if (req.path.startsWith("/api/")) return res.status(500).json({ ok: false, error: "Something went wrong. Please try again." });
  res.status(500).send("Something went wrong.");
});

// Only start listening when run directly (not when imported by tests).
const isMain = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  app.listen(PORT, () => {
    console.log(`\n  🍺  The Queen Victoria is open for business`);
    console.log(`      Local:  http://localhost:${PORT}`);
    console.log(`      Concierge: ${process.env.ANTHROPIC_API_KEY ? "Claude (" + (process.env.ANTHROPIC_MODEL || "claude-opus-4-8") + ")" : "local knowledge base (set ANTHROPIC_API_KEY for AI mode)"}\n`);
  });
}

export default app;
