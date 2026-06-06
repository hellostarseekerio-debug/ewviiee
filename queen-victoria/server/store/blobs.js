// Netlify Blobs-backed store (production on Netlify). Persistent key/value
// storage — no external database or extra account required.
//
// Key layout:
//   res/<REF>                          -> full reservation JSON (canonical, for lookup)
//   slot/<date>/<time>/<size>/<REF>    -> "" (existence = an active seat hold; size in the key)
//   enq/<id>                           -> enquiry JSON
//   sub/<email>                        -> subscriber JSON
//
// Encoding party size in the slot key lets availability sum seats from a single
// prefix `list()` without reading every reservation.

import { getStore } from "@netlify/blobs";

let _store;
function s() {
  if (!_store) _store = getStore({ name: "queen-victoria", consistency: "strong" });
  return _store;
}

const slotKey = (date, time, size, ref) => `slot/${date}/${time}/${size}/${ref}`;

async function listKeys(prefix) {
  const out = [];
  // Newer SDKs expose an async-iterable via list(); fall back to a single page.
  const res = await s().list({ prefix });
  for (const b of res.blobs || []) out.push(b.key);
  return out;
}

export const store = {
  async seatsByDate(date) {
    const keys = await listKeys(`slot/${date}/`);
    const byTime = new Map();
    for (const key of keys) {
      const [, , time, size] = key.split("/"); // slot/<date>/<time>/<size>/<ref>
      byTime.set(time, (byTime.get(time) || 0) + (Number.parseInt(size, 10) || 0));
    }
    return [...byTime.entries()].map(([time, seats]) => ({ time, seats }));
  },

  async seatsForSlot(date, time) {
    const keys = await listKeys(`slot/${date}/${time}/`);
    return keys.reduce((sum, key) => sum + (Number.parseInt(key.split("/")[3], 10) || 0), 0);
  },

  async insertReservation(rec) {
    const existing = await s().get(`res/${rec.reference}`);
    if (existing) throw new Error("UNIQUE reference collision");
    const record = { ...rec, created_at: new Date().toISOString() };
    await s().setJSON(`res/${rec.reference}`, record);
    if (rec.status !== "cancelled") {
      await s().set(slotKey(rec.date, rec.time, rec.party_size, rec.reference), "");
    }
  },

  async getReservation(ref) {
    return (await s().get(`res/${ref}`, { type: "json" })) || null;
  },

  async cancelReservation(ref) {
    const rec = await s().get(`res/${ref}`, { type: "json" });
    if (!rec || rec.status === "cancelled") return false;
    rec.status = "cancelled";
    await s().setJSON(`res/${ref}`, rec);
    await s().delete(slotKey(rec.date, rec.time, rec.party_size, ref));
    return true;
  },

  async insertEnquiry(obj) {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    await s().setJSON(`enq/${id}`, { ...obj, created_at: new Date().toISOString() });
  },

  async insertSubscriber(email) {
    await s().setJSON(`sub/${email}`, { email, created_at: new Date().toISOString() });
  },
};

export default store;
