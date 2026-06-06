/* Reservation flow: live availability, slot picker, validation, confirmation,
   and a "manage booking" lookup/cancel panel. */
(() => {
  "use strict";
  const $ = (s, c = document) => c.querySelector(s);
  const form = $("#reservation-form");
  if (!form) return;

  const dateInput = $("#res-date");
  const partyInput = $("#res-party");
  const slotsWrap = $("#res-slots");
  const slotsHint = $("#res-slots-hint");
  const timeField = $("#res-time");
  const status = $("#res-status");
  const submitBtn = form.querySelector('button[type="submit"]');
  const formView = $("#reservation-view");
  const confirmView = $("#confirmation-view");

  // Default date to today (HK), min today, max +120 days.
  const pad = (n) => String(n).padStart(2, "0");
  const fmt = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const today = new Date();
  dateInput.min = fmt(today);
  const max = new Date(today); max.setDate(max.getDate() + 120);
  dateInput.max = fmt(max);
  if (!dateInput.value) dateInput.value = fmt(today);

  let selectedTime = "";

  const setError = (name, msg) => {
    const field = form.querySelector(`[data-field="${name}"]`);
    if (!field) return;
    field.classList.toggle("invalid", !!msg);
    const err = field.querySelector(".field-error");
    if (err) err.textContent = msg || "";
  };
  const clearErrors = () => form.querySelectorAll(".field").forEach((f) => { f.classList.remove("invalid"); const e = f.querySelector(".field-error"); if (e) e.textContent = ""; });

  async function loadSlots() {
    selectedTime = ""; timeField.value = "";
    const date = dateInput.value;
    const party = partyInput.value || 2;
    if (!date) return;
    slotsWrap.innerHTML = '<p class="muted" style="grid-column:1/-1">Checking availability…</p>';
    try {
      const res = await fetch(`/api/reservations/availability?date=${encodeURIComponent(date)}&party=${party}`);
      const data = await res.json();
      if (!data.ok) { slotsWrap.innerHTML = `<p class="muted" style="grid-column:1/-1">${data.error || "Couldn't load times."}</p>`; return; }
      slotsWrap.innerHTML = "";
      const to12 = (t) => { let [h, m] = t.split(":").map(Number); const ap = h >= 12 ? "pm" : "am"; h = h % 12 || 12; return `${h}:${pad(m)} ${ap}`; };
      data.slots.forEach((s) => {
        const b = document.createElement("button");
        b.type = "button"; b.className = "slot"; b.textContent = to12(s.time); b.dataset.time = s.time;
        if (!s.available) b.disabled = true;
        b.addEventListener("click", () => {
          slotsWrap.querySelectorAll(".slot").forEach((x) => x.classList.remove("selected"));
          b.classList.add("selected"); selectedTime = s.time; timeField.value = s.time; setError("time", "");
        });
        slotsWrap.appendChild(b);
      });
      const anyLarge = data.slots[0]?.largeParty;
      slotsHint.textContent = anyLarge
        ? "For parties of 8 or more we'll personally confirm your booking after you request it."
        : "Times shown in Hong Kong time. Pick a slot to continue.";
    } catch {
      slotsWrap.innerHTML = '<p class="muted" style="grid-column:1/-1">Couldn\'t load availability. Please call 2529 7800.</p>';
    }
  }

  dateInput.addEventListener("change", loadSlots);
  partyInput.addEventListener("change", loadSlots);
  loadSlots();

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearErrors();
    if (!selectedTime) { setError("time", "Please choose a time."); slotsWrap.scrollIntoView({ behavior: "smooth", block: "center" }); return; }

    const payload = {
      name: $("#res-name").value,
      email: $("#res-email").value,
      phone: $("#res-phone").value,
      partySize: partyInput.value,
      date: dateInput.value,
      time: selectedTime,
      occasion: $("#res-occasion").value,
      notes: $("#res-notes").value,
    };

    submitBtn.disabled = true;
    const label = submitBtn.textContent;
    submitBtn.textContent = "Reserving…";
    status.className = "form-status";

    try {
      const res = await fetch("/api/reservations", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      });
      const data = await res.json();

      if (res.status === 422 && data.errors) {
        Object.entries(data.errors).forEach(([k, v]) => setError(k, v));
        status.className = "form-status error show";
        status.textContent = "Please check the highlighted fields.";
      } else if (!res.ok) {
        status.className = "form-status error show";
        status.textContent = data.error || "Something went wrong. Please try again or call 2529 7800.";
        if (res.status === 409) loadSlots();
      } else {
        // Success — render confirmation.
        const b = data.booking;
        const to12 = (t) => { let [h, m] = t.split(":").map(Number); const ap = h >= 12 ? "pm" : "am"; h = h % 12 || 12; return `${h}:${pad(m)} ${ap}`; };
        const dateNice = new Date(`${b.date}T00:00:00`).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
        $("#confirm-ref").textContent = b.reference;
        $("#confirm-detail").innerHTML =
          `<strong>${b.name}</strong> · party of ${b.partySize}<br>${dateNice} at ${to12(b.time)}`;
        $("#confirm-message").textContent = data.message;
        formView.style.display = "none";
        confirmView.style.display = "block";
        confirmView.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    } catch {
      status.className = "form-status error show";
      status.textContent = "Network error. Please try again or call us on 2529 7800.";
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = label;
    }
  });

  // "Book another" reset.
  $("#confirm-again")?.addEventListener("click", () => {
    form.reset(); clearErrors(); selectedTime = ""; timeField.value = "";
    dateInput.value = fmt(today);
    confirmView.style.display = "none"; formView.style.display = "block";
    loadSlots();
    formView.scrollIntoView({ behavior: "smooth", block: "start" });
  });

  /* ---- Manage booking (lookup / cancel) ---------------------------------- */
  const lookupForm = $("#lookup-form");
  lookupForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const ref = $("#lookup-ref").value.trim().toUpperCase();
    const out = $("#lookup-result");
    if (!ref) return;
    out.className = "form-status show"; out.textContent = "Looking up…";
    try {
      const res = await fetch(`/api/reservations/${encodeURIComponent(ref)}`);
      const data = await res.json();
      if (!data.ok) { out.className = "form-status error show"; out.textContent = data.error; return; }
      const b = data.booking;
      const dateNice = new Date(`${b.date}T00:00:00`).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });
      out.className = "form-status success show";
      out.innerHTML = `Booking <strong>${b.reference}</strong> — ${b.name}, party of ${b.partySize}, ${dateNice} at ${b.time}. Status: <strong>${b.status}</strong>. ` +
        (b.status !== "cancelled" ? `<button id="do-cancel" class="btn btn--dark" style="margin-top:1rem">Cancel this booking</button>` : "");
      $("#do-cancel")?.addEventListener("click", async () => {
        const c = await fetch(`/api/reservations/${encodeURIComponent(ref)}/cancel`, { method: "POST" });
        const cd = await c.json();
        out.className = `form-status ${c.ok ? "success" : "error"} show`;
        out.textContent = cd.message || cd.error;
      });
    } catch {
      out.className = "form-status error show"; out.textContent = "Couldn't look that up. Please try again.";
    }
  });
})();
