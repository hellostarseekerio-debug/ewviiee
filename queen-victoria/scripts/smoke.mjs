/* End-to-end smoke test: boots the app on an ephemeral port and exercises
   every endpoint. Run: `node scripts/smoke.mjs`. */
import app from "../server/index.js";

let pass = 0, fail = 0;
const ok = (cond, label) => { if (cond) { pass++; console.log("  ✓", label); } else { fail++; console.error("  ✗", label); } };

const server = app.listen(0);
await new Promise((r) => server.once("listening", r));
const base = `http://localhost:${server.address().port}`;
const j = (p, opts) => fetch(base + p, opts).then(async (r) => ({ status: r.status, body: await r.json().catch(() => ({})) }));

try {
  console.log("\nHealth & info");
  ok((await j("/api/health")).body.ok === true, "GET /api/health");
  ok((await j("/api/info")).body.name === "The Queen Victoria", "GET /api/info");

  console.log("\nMenu");
  const menu = await j("/api/menu");
  ok(menu.body.ok && menu.body.categories.length >= 8, "GET /api/menu returns categories");
  const veg = await j("/api/menu?tag=ve");
  ok(veg.body.categories.every((c) => c.items.every((i) => i.tags.includes("ve"))), "GET /api/menu?tag=ve filters vegan");

  console.log("\nReservations");
  const d = new Date(Date.now() + 3 * 86400000).toISOString().slice(0, 10);
  const avail = await j(`/api/reservations/availability?date=${d}&party=2`);
  ok(avail.body.ok && avail.body.slots.length > 0, "GET availability returns slots");
  const slot = avail.body.slots.find((s) => s.available)?.time || "19:00";

  const create = await j("/api/reservations", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: "Alice Smith", email: "alice@example.com", phone: "98765432", partySize: 4, date: d, time: slot, occasion: "Birthday" }) });
  ok(create.status === 201 && create.body.ok && /^[A-Z0-9]{6}$/.test(create.body.reference), "POST creates booking with reference");
  const ref = create.body.reference;
  ok(create.body.status === "confirmed", "small party auto-confirmed");

  const big = await j("/api/reservations", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: "Bob Jones", email: "bob@example.com", phone: "98765432", partySize: 12, date: d, time: slot }) });
  ok(big.body.status === "pending", "large party (12) flagged pending");

  const bad = await j("/api/reservations", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: "X", email: "nope", phone: "1", partySize: 99, date: "bad", time: "99:99" }) });
  ok(bad.status === 422 && bad.body.errors, "POST rejects invalid payload (422 + errors)");

  const lookup = await j(`/api/reservations/${ref}`);
  ok(lookup.body.ok && lookup.body.booking.name === "Alice Smith", "GET booking by reference");

  const cancel = await j(`/api/reservations/${ref}/cancel`, { method: "POST" });
  ok(cancel.body.ok, "POST cancels booking");
  const lookup2 = await j(`/api/reservations/${ref}`);
  ok(lookup2.body.booking.status === "cancelled", "cancelled status persisted");

  console.log("\nContact & newsletter");
  const contact = await j("/api/contact", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: "Cara", email: "cara@example.com", message: "Can I book for 10?", type: "private-event" }) });
  ok(contact.status === 201 && contact.body.ok, "POST /api/contact (private-event)");
  const news = await j("/api/contact/newsletter", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: "fan@example.com" }) });
  ok(news.status === 201 && news.body.ok, "POST /api/contact/newsletter");
  const newsBad = await j("/api/contact/newsletter", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: "nope" }) });
  ok(newsBad.status === 422, "newsletter rejects bad email");

  console.log("\nAI concierge (fallback mode, SSE)");
  const chatRes = await fetch(base + "/api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: "when is happy hour?" }) });
  ok(chatRes.headers.get("content-type")?.includes("text/event-stream"), "chat returns SSE stream");
  const text = await chatRes.text();
  ok(/event: delta/.test(text) && /event: done/.test(text), "chat streams delta + done events");
  ok(/happy hour/i.test(text), "chat fallback answers happy-hour question");

  console.log("\nSEO");
  const sm = await fetch(base + "/sitemap.xml").then((r) => r.text());
  ok(sm.includes("<urlset") && sm.includes("/menu.html"), "GET /sitemap.xml");
  const rb = await fetch(base + "/robots.txt").then((r) => r.text());
  ok(rb.includes("Sitemap:") && rb.includes("Disallow: /api/"), "GET /robots.txt");
  const sd = await j("/structured-data.json");
  ok(sd.body["@type"] === "BarOrPub" && sd.body.aggregateRating, "GET /structured-data.json (JSON-LD)");

  console.log("\nStatic pages");
  for (const p of ["/", "/menu.html", "/reservations.html", "/events.html", "/about.html", "/gallery.html", "/contact.html"]) {
    const r = await fetch(base + p);
    ok(r.status === 200 && (await r.text()).includes("The Queen Victoria"), `GET ${p}`);
  }
  const nf = await fetch(base + "/does-not-exist");
  ok(nf.status === 404, "unknown page returns 404");
  const apiNf = await j("/api/nope");
  ok(apiNf.status === 404 && apiNf.body.ok === false, "unknown API route returns JSON 404");

} catch (err) {
  console.error("Test threw:", err);
  fail++;
} finally {
  server.close();
  console.log(`\n${fail === 0 ? "✅" : "❌"} ${pass} passed, ${fail} failed\n`);
  process.exit(fail === 0 ? 0 : 1);
}
