// Generates static SEO files into public/ at build time so they're served from
// the CDN (no function invocation). Run by the Netlify build command.
// SITE_URL resolves from Netlify's `URL` env var in production.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { restaurant } from "../server/data/restaurant.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const publicDir = path.join(__dirname, "..", "public");
const SITE_URL = (process.env.URL || process.env.SITE_URL || "https://thequeenvictoriahk.com").replace(/\/$/, "");

const PAGES = [
  { loc: "/", priority: "1.0", changefreq: "weekly" },
  { loc: "/menu.html", priority: "0.9", changefreq: "weekly" },
  { loc: "/reservations.html", priority: "0.9", changefreq: "monthly" },
  { loc: "/events.html", priority: "0.8", changefreq: "weekly" },
  { loc: "/about.html", priority: "0.7", changefreq: "monthly" },
  { loc: "/gallery.html", priority: "0.6", changefreq: "monthly" },
  { loc: "/contact.html", priority: "0.7", changefreq: "monthly" },
];

const today = new Date().toISOString().slice(0, 10);
const sitemap = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${PAGES.map((p) => `  <url><loc>${SITE_URL}${p.loc}</loc><lastmod>${today}</lastmod><changefreq>${p.changefreq}</changefreq><priority>${p.priority}</priority></url>`).join("\n")}
</urlset>`;
fs.writeFileSync(path.join(publicDir, "sitemap.xml"), sitemap);

fs.writeFileSync(path.join(publicDir, "robots.txt"), `User-agent: *\nAllow: /\nDisallow: /api/\n\nSitemap: ${SITE_URL}/sitemap.xml\n`);

const r = restaurant;
const structured = {
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
  address: { "@type": "PostalAddress", streetAddress: `${r.address.line1}, ${r.address.line2}`, addressLocality: r.address.district, addressRegion: r.address.city, addressCountry: "HK" },
  geo: { "@type": "GeoCoordinates", latitude: r.geo.latitude, longitude: r.geo.longitude },
  aggregateRating: { "@type": "AggregateRating", ratingValue: r.ratings.average, reviewCount: r.ratings.count },
  openingHoursSpecification: r.hours.map((h) => ({ "@type": "OpeningHoursSpecification", dayOfWeek: h.day, opens: h.open, closes: h.close === "00:00" ? "23:59" : h.close })),
  acceptsReservations: `${SITE_URL}/reservations.html`,
  sameAs: [r.social.instagram, r.social.facebook],
};
fs.writeFileSync(path.join(publicDir, "structured-data.json"), JSON.stringify(structured, null, 2));

console.log(`SEO files written for ${SITE_URL}`);
