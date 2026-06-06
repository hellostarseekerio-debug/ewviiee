// Netlify Function (v2) serving the entire /api/* surface for The Queen Victoria.
// Reuses the shared domain logic; persists via Netlify Blobs; streams the AI
// concierge over Server-Sent Events. Imports only pure-JS/SDK modules (no
// Express, no better-sqlite3) so it bundles cleanly for the serverless runtime.

import { store } from "../../server/store/blobs.js";
import { getAvailability, createReservation, lookupReservation, cancelReservation } from "../../server/booking.js";
import { validateEnquiry, EMAIL_RE, clean } from "../../server/middleware/validate.js";
import { streamReply, hasKey, MODEL } from "../../server/concierge.js";
import { restaurant } from "../../server/data/restaurant.js";
import { menu, tagLabels } from "../../server/data/menu.js";

export const config = { path: "/api/*" };

const json = (status, body) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

// Best-effort in-memory rate limiting (per warm instance). Netlify's platform
// provides the primary DDoS protection; this guards token spend & spam.
const buckets = new Map();
function limited(key, max, windowMs) {
  const now = Date.now();
  const b = buckets.get(key);
  if (!b || now > b.reset) { buckets.set(key, { count: 1, reset: now + windowMs }); return false; }
  b.count += 1;
  return b.count > max;
}
const ipOf = (req) => (req.headers.get("x-nf-client-connection-ip") || req.headers.get("x-forwarded-for") || "anon").split(",")[0].trim();

export default async (req) => {
  const url = new URL(req.url);
  const path = url.pathname.replace(/\/+$/, "") || "/api";
  const method = req.method.toUpperCase();
  const ip = ipOf(req);

  const readBody = async () => { try { return await req.json(); } catch { return {}; } };

  try {
    // --- Health & info ---
    if (path === "/api/health") return json(200, { ok: true, service: "the-queen-victoria", time: new Date().toISOString() });
    if (path === "/api/info") {
      return json(200, {
        ok: true, name: restaurant.name, tagline: restaurant.tagline, contact: restaurant.contact,
        address: restaurant.address, hours: restaurant.hours, hoursSummary: restaurant.hoursSummary,
        features: restaurant.features, highlights: restaurant.highlights, faq: restaurant.faq, ratings: restaurant.ratings,
      });
    }

    // --- Menu ---
    if (path === "/api/menu" && method === "GET") {
      const tag = url.searchParams.get("tag");
      const categoryId = url.searchParams.get("category");
      let categories = menu.categories;
      if (categoryId) categories = categories.filter((c) => c.id === categoryId);
      if (tag) categories = categories.map((c) => ({ ...c, items: c.items.filter((i) => i.tags.includes(tag)) })).filter((c) => c.items.length);
      return json(200, { ok: true, currency: menu.currency, note: menu.note, tagLabels, categories });
    }

    // --- Reservations ---
    if (path === "/api/reservations/availability" && method === "GET") {
      const result = await getAvailability(store, url.searchParams.get("date"), url.searchParams.get("party"));
      return result.error ? json(400, { ok: false, error: result.error }) : json(200, result);
    }
    if (path === "/api/reservations" && method === "POST") {
      if (limited(`res:${ip}`, 20, 3600_000)) return json(429, { ok: false, error: "Too many requests. Please try again later or call 2529 7800." });
      const { status, body } = await createReservation(store, await readBody());
      return json(status, body);
    }
    const cancelMatch = path.match(/^\/api\/reservations\/([^/]+)\/cancel$/);
    if (cancelMatch && method === "POST") {
      const { status, body } = await cancelReservation(store, cancelMatch[1]);
      return json(status, body);
    }
    const refMatch = path.match(/^\/api\/reservations\/([^/]+)$/);
    if (refMatch && method === "GET") {
      const { status, body } = await lookupReservation(store, refMatch[1]);
      return json(status, body);
    }

    // --- Contact & newsletter ---
    if (path === "/api/contact" && method === "POST") {
      if (limited(`contact:${ip}`, 20, 3600_000)) return json(429, { ok: false, error: "Too many requests. Please try again later." });
      const { valid, errors, value } = validateEnquiry(await readBody());
      if (!valid) return json(422, { ok: false, errors });
      await store.insertEnquiry(value);
      return json(201, { ok: true, message: value.type === "private-event"
        ? "Thank you — your event enquiry is with our team. We'll be in touch within one working day."
        : "Thank you for getting in touch. We'll reply as soon as we can." });
    }
    if (path === "/api/contact/newsletter" && method === "POST") {
      const email = clean((await readBody()).email, 160).toLowerCase();
      if (!EMAIL_RE.test(email)) return json(422, { ok: false, errors: { email: "Please enter a valid email address." } });
      await store.insertSubscriber(email);
      return json(201, { ok: true, message: "You're on the list. Cheers — see you at the bar." });
    }

    // --- AI Concierge (streaming SSE) ---
    if (path === "/api/chat" && method === "POST") {
      if (limited(`chat:${ip}`, 30, 300_000)) return json(429, { ok: false, error: "The concierge is catching its breath. Please wait a moment." });
      const data = await readBody();
      const message = clean(data.message, 1500);
      if (!message) return json(422, { ok: false, error: "Please type a message for the concierge." });

      const enc = new TextEncoder();
      const sse = (event, data) => enc.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);

      const stream = new ReadableStream({
        async start(controller) {
          controller.enqueue(sse("start", { model: hasKey ? MODEL : "concierge-local", powered: hasKey }));
          let full = "";
          try {
            for await (const chunk of streamReply(message, data.history)) { full += chunk; controller.enqueue(sse("delta", { text: chunk })); }
            controller.enqueue(sse("done", { text: full }));
          } catch (err) {
            controller.enqueue(sse("done", { text: full || "Apologies — please call us on 2529 7800.", degraded: true }));
          } finally {
            controller.close();
          }
        },
      });
      return new Response(stream, { headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no" } });
    }

    return json(404, { ok: false, error: "Not found." });
  } catch (err) {
    console.error("[api] error:", err?.message || err);
    return json(500, { ok: false, error: "Something went wrong. Please try again." });
  }
};
