import { Router } from "express";
import store from "../store/sqlite.js";
import { getAvailability, createReservation, lookupReservation, cancelReservation } from "../booking.js";
import { writeLimiter } from "../middleware/rateLimit.js";

const router = Router();

// GET /api/reservations/availability?date=YYYY-MM-DD&party=4
router.get("/availability", async (req, res, next) => {
  try {
    const result = await getAvailability(store, req.query.date, req.query.party);
    if (result.error) return res.status(400).json({ ok: false, error: result.error });
    res.json(result);
  } catch (e) { next(e); }
});

// POST /api/reservations
router.post("/", writeLimiter, async (req, res, next) => {
  try {
    const { status, body } = await createReservation(store, req.body || {});
    res.status(status).json(body);
  } catch (e) { next(e); }
});

// GET /api/reservations/:reference
router.get("/:reference", async (req, res, next) => {
  try {
    const { status, body } = await lookupReservation(store, req.params.reference);
    res.status(status).json(body);
  } catch (e) { next(e); }
});

// POST /api/reservations/:reference/cancel
router.post("/:reference/cancel", writeLimiter, async (req, res, next) => {
  try {
    const { status, body } = await cancelReservation(store, req.params.reference);
    res.status(status).json(body);
  } catch (e) { next(e); }
});

export default router;
