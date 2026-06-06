// Validates the Netlify function module: clean import (no better-sqlite3 in the
// graph), routing, and the streaming concierge — plus the shared booking logic
// the Blobs path relies on, exercised against an in-memory mock store.
import handler from "../netlify/functions/api.mjs";
import { getAvailability, createReservation, lookupReservation, cancelReservation } from "../server/booking.js";

let pass = 0, fail = 0;
const ok = (c, l) => { if (c) { pass++; console.log("  ✓", l); } else { fail++; console.error("  ✗", l); } };
const call = (path, init) => handler(new Request("http://x" + path, init));

console.log("\nNetlify function routing (non-blob routes)");
let r = await call("/api/health");
ok(r.status === 200 && (await r.json()).ok, "GET /api/health");
r = await call("/api/menu");
const mb = await r.json();
ok(mb.ok && mb.categories.length >= 8, "GET /api/menu");
r = await call("/api/nope");
ok(r.status === 404, "unknown route -> 404");

console.log("\nNetlify function streaming concierge (fallback)");
r = await call("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: "when is happy hour?" }) });
ok(r.headers.get("content-type")?.includes("text/event-stream"), "chat returns SSE");
const text = await r.text();
ok(/event: delta/.test(text) && /event: done/.test(text), "chat streams delta + done");
ok(/happy hour/i.test(text), "chat answers happy-hour");

console.log("\nShared booking logic (in-memory mock store = Blobs behaviour)");
// Mock store mirroring the Blobs key model.
const seats = new Map(); // key: date|time|ref -> {size, status}
const res = new Map();   // ref -> record
const mock = {
  async seatsByDate(date) {
    const m = new Map();
    for (const [k, v] of seats) { const [d, t] = k.split("|"); if (d === date) m.set(t, (m.get(t) || 0) + v.size); }
    return [...m.entries()].map(([time, s]) => ({ time, seats: s }));
  },
  async seatsForSlot(date, time) { let s = 0; for (const [k, v] of seats) { const [d, t] = k.split("|"); if (d === date && t === time) s += v.size; } return s; },
  async insertReservation(rec) { if (res.has(rec.reference)) throw new Error("UNIQUE"); res.set(rec.reference, { ...rec }); if (rec.status !== "cancelled") seats.set(`${rec.date}|${rec.time}|${rec.reference}`, { size: rec.party_size }); },
  async getReservation(ref) { return res.get(ref) || null; },
  async cancelReservation(ref) { const r = res.get(ref); if (!r || r.status === "cancelled") return false; r.status = "cancelled"; seats.delete(`${r.date}|${r.time}|${ref}`); return true; },
  async insertEnquiry() {}, async insertSubscriber() {},
};

const d = new Date(Date.now() + 3 * 86400000).toISOString().slice(0, 10);
const av = await getAvailability(mock, d, 2);
ok(av.ok && av.slots.some((s) => s.available), "availability via mock store");
const slot = av.slots.find((s) => s.available).time;
const created = await createReservation(mock, { name: "Test Guest", email: "t@e.com", phone: "98765432", partySize: 4, date: d, time: slot });
ok(created.status === 201 && created.body.reference, "create via mock store");
const ref = created.body.reference;
const look = await lookupReservation(mock, ref);
ok(look.body.booking.name === "Test Guest", "lookup via mock store");
// Capacity: fill the slot, expect 409.
await createReservation(mock, { name: "Big", email: "b@e.com", phone: "98765432", partySize: 20, date: d, time: slot });
const full = await createReservation(mock, { name: "Over", email: "o@e.com", phone: "98765432", partySize: 20, date: d, time: slot });
ok(full.status === 409, "capacity enforced (409 when slot full)");
const canc = await cancelReservation(mock, ref);
ok(canc.body.ok, "cancel via mock store");
ok((await lookupReservation(mock, ref)).body.booking.status === "cancelled", "cancel persisted; seats freed");

console.log(`\n${fail === 0 ? "✅" : "❌"} ${pass} passed, ${fail} failed\n`);
process.exit(fail === 0 ? 0 : 1);
