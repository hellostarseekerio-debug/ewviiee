/* Contact & private-event enquiry form submission. */
(() => {
  "use strict";
  const form = document.getElementById("contact-form");
  if (!form) return;
  const status = document.getElementById("contact-status");
  const submitBtn = form.querySelector('button[type="submit"]');

  const setError = (name, msg) => {
    const field = form.querySelector(`[data-field="${name}"]`);
    if (!field) return;
    field.classList.toggle("invalid", !!msg);
    const err = field.querySelector(".field-error");
    if (err) err.textContent = msg || "";
  };
  const clearErrors = () => form.querySelectorAll(".field").forEach((f) => { f.classList.remove("invalid"); const e = f.querySelector(".field-error"); if (e) e.textContent = ""; });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearErrors();
    const payload = {
      name: form.name.value,
      email: form.email.value,
      phone: form.phone.value,
      subject: form.subject.value,
      message: form.message.value,
      type: form.dataset.type || form.type_field?.value || "general",
    };
    submitBtn.disabled = true;
    const label = submitBtn.textContent;
    submitBtn.textContent = "Sending…";
    status.className = "form-status";
    try {
      const res = await fetch("/api/contact", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (res.status === 422 && data.errors) {
        Object.entries(data.errors).forEach(([k, v]) => setError(k, v));
        status.className = "form-status error show";
        status.textContent = "Please check the highlighted fields.";
      } else if (!res.ok) {
        status.className = "form-status error show";
        status.textContent = data.error || "Something went wrong. Please try again.";
      } else {
        status.className = "form-status success show";
        status.textContent = data.message;
        form.reset();
      }
    } catch {
      status.className = "form-status error show";
      status.textContent = "Network error. Please try again or call 2529 7800.";
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = label;
    }
  });
})();
