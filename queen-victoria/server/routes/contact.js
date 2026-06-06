import { Router } from "express";
import store from "../store/sqlite.js";
import { validateEnquiry, EMAIL_RE, clean } from "../middleware/validate.js";
import { writeLimiter } from "../middleware/rateLimit.js";

const router = Router();

// POST /api/contact — general enquiry / private-event / feedback
router.post("/", writeLimiter, async (req, res, next) => {
  try {
    const { valid, errors, value } = validateEnquiry(req.body || {});
    if (!valid) return res.status(422).json({ ok: false, errors });
    await store.insertEnquiry(value);
    res.status(201).json({
      ok: true,
      message:
        value.type === "private-event"
          ? "Thank you — your event enquiry is with our team. We'll be in touch within one working day."
          : "Thank you for getting in touch. We'll reply as soon as we can.",
    });
  } catch (e) { next(e); }
});

// POST /api/newsletter — email sign-up
router.post("/newsletter", writeLimiter, async (req, res, next) => {
  try {
    const email = clean(req.body?.email, 160).toLowerCase();
    if (!EMAIL_RE.test(email)) return res.status(422).json({ ok: false, errors: { email: "Please enter a valid email address." } });
    await store.insertSubscriber(email);
    res.status(201).json({ ok: true, message: "You're on the list. Cheers — see you at the bar." });
  } catch (e) { next(e); }
});

export default router;
