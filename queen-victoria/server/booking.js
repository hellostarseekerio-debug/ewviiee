// Reservation domain logic, independent of transport and storage. Both the
// local Express routes and the Netlify function call these, passing an async
// `store` adapter (SQLite locally, Netlify Blobs in production).

import { customAlphabet } from "nanoid";
import { restaurant } from "./data/restaurant.js";
import { validateReservation, isValidDate } from "./middleware/validate.js";

export const policy = restaurant.reservation;

// Total seats the dining room can turn in a single 30-minute slot.
export const SLOT_CAPACITY = 40;

// Human-friendly, unambiguous reference codes (no 0/O/1/I).
const makeRef = customAlphabet("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", 6);

export function timeSlots() {
  const slots = [];
  const [sh, sm] = policy.firstSeating.split(":").map(Number);
  const [eh, em] = policy.lastSeating.split(":").map(Number);
  let mins = sh * 60 + sm;
  const end = eh * 60 + em;
  while (mins <= end) {
    slots.push(`${String(Math.floor(mins / 60)).padStart(2, "0")}:${String(mins % 60).padStart(2, "0")}`);
    mins += policy.slotIntervalMinutes;
  }
  return slots;
}

// store: { seatsByDate(date)->[{time,seats}], seatsForSlot(date,time)->number,
//          insertReservation(rec), getReservation(ref), cancelReservation(ref)->bool,
//          insertEnquiry(obj), insertSubscriber(email) }

export async function getAvailability(store, dateRaw, partyRaw) {
  const date = String(dateRaw || "");
  const party = Math.max(1, Number.parseInt(partyRaw, 10) || 2);
  if (!isValidDate(date)) return { error: "Please provide a valid date (YYYY-MM-DD)." };

  const booked = new Map();
  for (const row of await store.seatsByDate(date)) booked.set(row.time, row.seats);

  const earliest = new Date(Date.now() + policy.leadHours * 3600 * 1000);
  const slots = timeSlots().map((time) => {
    const seatsTaken = booked.get(time) || 0;
    const remaining = Math.max(0, SLOT_CAPACITY - seatsTaken);
    const available = remaining >= party && new Date(`${date}T${time}:00`) >= earliest;
    return { time, remaining, available, largeParty: party >= policy.largePartyThreshold };
  });
  return { ok: true, date, party, slots };
}

export async function createReservation(store, body) {
  const { valid, errors, value } = validateReservation(body || {}, policy);
  if (!valid) return { status: 422, body: { ok: false, errors } };

  const taken = await store.seatsForSlot(value.date, value.time);
  if (taken + value.party_size > SLOT_CAPACITY) {
    return { status: 409, body: { ok: false, error: "We're fully booked for that time. Please try another slot, or call us on 2529 7800." } };
  }

  const status = value.party_size >= policy.largePartyThreshold ? "pending" : "confirmed";
  let reference = makeRef();
  try {
    await store.insertReservation({ ...value, reference, status });
  } catch (err) {
    if (String(err?.message).includes("UNIQUE")) {
      reference = makeRef();
      await store.insertReservation({ ...value, reference, status });
    } else throw err;
  }

  return {
    status: 201,
    body: {
      ok: true,
      reference,
      status,
      message:
        status === "pending"
          ? "Thank you — your request for a large party is in. Our team will confirm by email or phone shortly."
          : "Your table is booked. We can't wait to welcome you to The Queen Victoria.",
      booking: { reference, name: value.name, date: value.date, time: value.time, partySize: value.party_size, status },
    },
  };
}

export async function lookupReservation(store, refRaw) {
  const row = await store.getReservation(String(refRaw).toUpperCase());
  if (!row) return { status: 404, body: { ok: false, error: "No booking found with that reference." } };
  return {
    status: 200,
    body: { ok: true, booking: { reference: row.reference, name: row.name, date: row.date, time: row.time, partySize: row.party_size, occasion: row.occasion, status: row.status } },
  };
}

export async function cancelReservation(store, refRaw) {
  const changed = await store.cancelReservation(String(refRaw).toUpperCase());
  if (!changed) return { status: 404, body: { ok: false, error: "No active booking found with that reference." } };
  return { status: 200, body: { ok: true, message: "Your booking has been cancelled. We hope to see you another time." } };
}
