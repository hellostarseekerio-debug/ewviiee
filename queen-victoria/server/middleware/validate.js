// Small, dependency-free validation helpers. We keep validation explicit and
// readable rather than pulling in a schema library for a handful of fields.

export const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
export const TIME_RE = /^([01]\d|2[0-3]):([0-5]\d)$/;
export const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

export function clean(value, maxLen = 500) {
  if (typeof value !== "string") return "";
  return value.trim().slice(0, maxLen);
}

export function isValidDate(str) {
  if (!DATE_RE.test(str)) return false;
  const d = new Date(`${str}T00:00:00`);
  return !Number.isNaN(d.getTime()) && str === d.toISOString().slice(0, 10);
}

// Returns { valid, errors, value } for a reservation payload.
export function validateReservation(body, policy) {
  const errors = {};
  const value = {
    name: clean(body.name, 120),
    email: clean(body.email, 160).toLowerCase(),
    phone: clean(body.phone, 40),
    occasion: clean(body.occasion, 60),
    notes: clean(body.notes, 600),
    date: clean(body.date, 10),
    time: clean(body.time, 5),
    party_size: Number.parseInt(body.partySize ?? body.party_size, 10),
  };

  if (value.name.length < 2) errors.name = "Please give us a name for the booking.";
  if (!EMAIL_RE.test(value.email)) errors.email = "Please enter a valid email address.";
  if (value.phone.replace(/\D/g, "").length < 6) errors.phone = "Please enter a contactable phone number.";
  if (!Number.isInteger(value.party_size) || value.party_size < policy.minPartySize || value.party_size > policy.maxPartySize)
    errors.partySize = `Party size must be between ${policy.minPartySize} and ${policy.maxPartySize}.`;
  if (!isValidDate(value.date)) errors.date = "Please choose a valid date.";
  if (!TIME_RE.test(value.time)) errors.time = "Please choose a valid time.";

  // Booking must be in the future (respecting the lead time) and not absurdly far out.
  if (!errors.date && !errors.time) {
    const when = new Date(`${value.date}T${value.time}:00`);
    const earliest = new Date(Date.now() + policy.leadHours * 3600 * 1000);
    const latest = new Date(Date.now() + 120 * 24 * 3600 * 1000); // 120 days
    if (when < earliest) errors.time = "Please book at least an hour ahead. For sooner, call us on 2529 7800.";
    else if (when > latest) errors.date = "We take bookings up to 120 days in advance.";
    else if (value.time < policy.firstSeating || value.time > policy.lastSeating)
      errors.time = `Online bookings run from ${policy.firstSeating} to ${policy.lastSeating}. For later, give us a call.`;
  }

  return { valid: Object.keys(errors).length === 0, errors, value };
}

export function validateEnquiry(body) {
  const errors = {};
  const allowedTypes = new Set(["general", "private-event", "feedback"]);
  const value = {
    name: clean(body.name, 120),
    email: clean(body.email, 160).toLowerCase(),
    phone: clean(body.phone, 40),
    subject: clean(body.subject, 160),
    message: clean(body.message, 2000),
    type: allowedTypes.has(body.type) ? body.type : "general",
  };
  if (value.name.length < 2) errors.name = "Please tell us your name.";
  if (!EMAIL_RE.test(value.email)) errors.email = "Please enter a valid email address.";
  if (value.message.length < 5) errors.message = "Please include a short message.";
  return { valid: Object.keys(errors).length === 0, errors, value };
}

export default { validateReservation, validateEnquiry, clean, isValidDate, EMAIL_RE, TIME_RE, DATE_RE };
