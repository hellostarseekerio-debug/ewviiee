import { Router } from "express";
import { customAlphabet } from "nanoid";
import { statements } from "../db.js";
import { restaurant } from "../data/restaurant.js";
import { validateReservation, isValidDate } from "../middleware/validate.js";
import { writeLimiter } from "../middleware/rateLimit.js";

const router = Router();
const policy = restaurant.reservation;

// Human-friendly, unambiguous reference codes (no 0/O/1/I).
const makeRef = customAlphabet("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", 6);

// Total seats the dining room can turn in a single 30-minute slot.
const SLOT_CAPACITY = 40;

function timeSlots() {
  const slots = [];
  const [sh, sm] = policy.firstSeating.split(":").map(Number);
  const [eh, em] = policy.lastSeating.split(":").map(Number);
  let mins = sh * 60 + sm;
  const end = eh * 60 + em;
  while (mins <= end) {
    const h = String(Math.floor(mins / 60)).padStart(2, "0");
    const m = String(mins % 60).padStart(2, "0");
    slots.push(`${h}:${m}`);
    mins += policy.slotIntervalMinutes;
  }
  return slots;
}

// GET /api/reservations/availability?date=YYYY-MM-DD&party=4
// Returns each slot with remaining capacity so the UI can grey out full times.
router.get("/availability", (req, res) => {
  const date = String(req.query.date || "");
  const party = Math.max(1, Number.parseInt(req.query.party, 10) || 2);
  if (!isValidDate(date)) {
    return res.status(400).json({ ok: false, error: "Please provide a valid date (YYYY-MM-DD)." });
  }

  const booked = new Map();
  for (const row of statements.seatsByDate.all(date)) booked.set(row.time, row.seats);

  const now = new Date();
  const earliest = new Date(now.getTime() + policy.leadHours * 3600 * 1000);

  const slots = timeSlots().map((time) => {
    const seatsTaken = booked.get(time) || 0;
    const remaining = Math.max(0, SLOT_CAPACITY - seatsTaken);
    const slotTime = new Date(`${date}T${time}:00`);
    const available = remaining >= party && slotTime >= earliest;
    return {
      time,
      remaining,
      available,
      largeParty: party >= policy.largePartyThreshold,
    };
  });

  res.json({ ok: true, date, party, slots });
});

// POST /api/reservations  — create a booking
router.post("/", writeLimiter, (req, res) => {
  const { valid, errors, value } = validateReservation(req.body || {}, policy);
  if (!valid) return res.status(422).json({ ok: false, errors });

  // Capacity check (defends against the form being bypassed).
  const taken = statements.countSeatsForSlot.get(value.date, value.time).seats;
  if (taken + value.party_size > SLOT_CAPACITY) {
    return res.status(409).json({
      ok: false,
      error: "We're fully booked for that time. Please try another slot, or call us on 2529 7800.",
    });
  }

  // Large parties are accepted but flagged for the team to confirm details.
  const status = value.party_size >= policy.largePartyThreshold ? "pending" : "confirmed";
  const reference = makeRef();

  try {
    statements.insertReservation.run({ ...value, reference, status });
  } catch (err) {
    if (String(err.message).includes("UNIQUE")) {
      // Reference collision — astronomically unlikely; retry once.
      statements.insertReservation.run({ ...value, reference: makeRef(), status });
    } else {
      throw err;
    }
  }

  res.status(201).json({
    ok: true,
    reference,
    status,
    message:
      status === "pending"
        ? "Thank you — your request for a large party is in. Our team will confirm by email or phone shortly."
        : "Your table is booked. We can't wait to welcome you to The Queen Victoria.",
    booking: {
      reference,
      name: value.name,
      date: value.date,
      time: value.time,
      partySize: value.party_size,
      status,
    },
  });
});

// GET /api/reservations/:reference — look up a booking
router.get("/:reference", (req, res) => {
  const row = statements.findByReference.get(String(req.params.reference).toUpperCase());
  if (!row) return res.status(404).json({ ok: false, error: "No booking found with that reference." });
  res.json({
    ok: true,
    booking: {
      reference: row.reference,
      name: row.name,
      date: row.date,
      time: row.time,
      partySize: row.party_size,
      occasion: row.occasion,
      status: row.status,
    },
  });
});

// POST /api/reservations/:reference/cancel — cancel a booking
router.post("/:reference/cancel", writeLimiter, (req, res) => {
  const ref = String(req.params.reference).toUpperCase();
  const result = statements.cancelByReference.run(ref);
  if (result.changes === 0) {
    return res.status(404).json({ ok: false, error: "No active booking found with that reference." });
  }
  res.json({ ok: true, message: "Your booking has been cancelled. We hope to see you another time." });
});

export default router;
