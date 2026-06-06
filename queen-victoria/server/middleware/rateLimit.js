// Tiered rate limiting. The booking and chat endpoints are more sensitive
// (they write to the DB / spend tokens) so they get tighter limits than the
// read-only menu/availability endpoints.

import rateLimit from "express-rate-limit";

const json = (message) => ({
  handler: (req, res) => res.status(429).json({ ok: false, error: message }),
  standardHeaders: true,
  legacyHeaders: false,
});

// Broad limiter applied to the whole API surface.
export const apiLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 300,
  ...json("Too many requests. Please slow down and try again shortly."),
});

// Writes (reservations, enquiries, newsletter): stop abuse / spam.
export const writeLimiter = rateLimit({
  windowMs: 60 * 60 * 1000, // 1 hour
  max: 20,
  ...json("You've made a lot of requests. Please try again in a little while, or call us on 2529 7800."),
});

// AI concierge: protect token spend.
export const chatLimiter = rateLimit({
  windowMs: 5 * 60 * 1000, // 5 minutes
  max: 30,
  ...json("The concierge is catching its breath. Please wait a moment before sending another message."),
});

export default { apiLimiter, writeLimiter, chatLimiter };
