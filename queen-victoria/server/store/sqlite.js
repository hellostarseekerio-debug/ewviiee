// SQLite-backed store (local development & self-hosting). Wraps the prepared
// statements in db.js behind the async store interface booking.js expects.

import db, { statements } from "../db.js";

export const store = {
  async seatsByDate(date) {
    return statements.seatsByDate.all(date);
  },
  async seatsForSlot(date, time) {
    return statements.countSeatsForSlot.get(date, time).seats;
  },
  async insertReservation(rec) {
    statements.insertReservation.run({
      reference: rec.reference,
      name: rec.name,
      email: rec.email,
      phone: rec.phone,
      party_size: rec.party_size,
      date: rec.date,
      time: rec.time,
      occasion: rec.occasion || null,
      notes: rec.notes || null,
      status: rec.status,
    });
  },
  async getReservation(ref) {
    return statements.findByReference.get(ref) || null;
  },
  async cancelReservation(ref) {
    return statements.cancelByReference.run(ref).changes > 0;
  },
  async insertEnquiry(obj) {
    statements.insertEnquiry.run({
      name: obj.name,
      email: obj.email,
      phone: obj.phone || null,
      subject: obj.subject || null,
      message: obj.message,
      type: obj.type,
    });
  },
  async insertSubscriber(email) {
    statements.insertSubscriber.run(email);
  },
};

export { db };
export default store;
