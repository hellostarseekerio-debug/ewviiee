/* Global site behaviour: navigation, scroll effects, reveal & parallax
   animations, animated counters, live "open now" status, newsletter. */
(() => {
  "use strict";
  const $ = (s, c = document) => c.querySelector(s);
  const $$ = (s, c = document) => [...c.querySelectorAll(s)];
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---- Mobile nav -------------------------------------------------------- */
  const toggle = $(".nav-toggle");
  const links = $(".nav-links");
  const backdrop = $(".nav-backdrop");
  const closeNav = () => { toggle?.classList.remove("open"); links?.classList.remove("open"); backdrop?.classList.remove("show"); document.body.style.overflow = ""; };
  toggle?.addEventListener("click", () => {
    const open = links.classList.toggle("open");
    toggle.classList.toggle("open", open);
    backdrop?.classList.toggle("show", open);
    document.body.style.overflow = open ? "hidden" : "";
  });
  backdrop?.addEventListener("click", closeNav);
  $$(".nav-links a").forEach((a) => a.addEventListener("click", closeNav));

  /* ---- Header on scroll -------------------------------------------------- */
  const header = $(".site-header");
  const onScroll = () => header?.classList.toggle("scrolled", window.scrollY > 40);
  onScroll();
  addEventListener("scroll", onScroll, { passive: true });

  /* ---- Reveal on scroll -------------------------------------------------- */
  const reveals = $$("[data-reveal]");
  if (reduce) {
    reveals.forEach((el) => el.classList.add("in"));
  } else if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } });
    }, { threshold: 0.12, rootMargin: "0px 0px -8% 0px" });
    reveals.forEach((el) => io.observe(el));
  } else {
    reveals.forEach((el) => el.classList.add("in"));
  }

  /* ---- Hero parallax ----------------------------------------------------- */
  const heroImg = $(".hero-bg img");
  if (heroImg && !reduce) {
    let ticking = false;
    addEventListener("scroll", () => {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(() => {
        const y = Math.min(window.scrollY, window.innerHeight) * 0.28;
        heroImg.style.transform = `translate3d(0, ${y}px, 0) scale(1.05)`;
        ticking = false;
      });
    }, { passive: true });
  }

  /* ---- Animated counters ------------------------------------------------- */
  const counters = $$("[data-count]");
  if (counters.length) {
    const animate = (el) => {
      const target = parseFloat(el.dataset.count);
      const dec = (el.dataset.count.split(".")[1] || "").length;
      const dur = 1600; const start = performance.now();
      const step = (now) => {
        const p = Math.min((now - start) / dur, 1);
        const eased = 1 - Math.pow(1 - p, 3);
        el.textContent = (target * eased).toFixed(dec) + (el.dataset.suffix || "");
        if (p < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    };
    const cio = new IntersectionObserver((entries) => {
      entries.forEach((e) => { if (e.isIntersecting) { animate(e.target); cio.unobserve(e.target); } });
    }, { threshold: 0.5 });
    counters.forEach((c) => (reduce ? (c.textContent = c.dataset.count + (c.dataset.suffix || "")) : cio.observe(c)));
  }

  /* ---- Ticker duplication (seamless loop) -------------------------------- */
  const track = $(".ticker-track");
  if (track) track.innerHTML += track.innerHTML;

  /* ---- Live "open now" + today highlight --------------------------------- */
  // Hours mirrored from the server knowledge base (HK time, 24h).
  const HOURS = {
    0: { open: "12:00", close: "24:00" }, // Sun
    1: { open: "12:00", close: "24:00" },
    2: { open: "12:00", close: "24:00" },
    3: { open: "12:00", close: "26:00" }, // Wed close 2am
    4: { open: "12:00", close: "28:00" }, // Thu close 4am
    5: { open: "12:00", close: "28:00" },
    6: { open: "12:00", close: "28:00" },
  };
  const hkNow = () => {
    const now = new Date();
    // Convert to HK time (UTC+8) regardless of viewer locale.
    const utc = now.getTime() + now.getTimezoneOffset() * 60000;
    return new Date(utc + 8 * 3600000);
  };
  const isOpenNow = () => {
    const n = hkNow();
    const mins = n.getHours() * 60 + n.getMinutes();
    const today = HOURS[n.getDay()];
    const yest = HOURS[(n.getDay() + 6) % 7];
    const toM = (s) => { const [h, m] = s.split(":").map(Number); return h * 60 + m; };
    if (mins >= toM(today.open) && mins < toM(today.close)) return true;       // normal window
    if (toM(yest.close) > 1440 && mins < toM(yest.close) - 1440) return true;  // spillover past midnight
    return false;
  };
  $$("[data-open-pill]").forEach((pill) => {
    const open = isOpenNow();
    pill.classList.add(open ? "open" : "closed");
    pill.innerHTML = `<span class="dot"></span>${open ? "Open now" : "Currently closed"}`;
  });
  const todayName = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"][hkNow().getDay()];
  $$(".hours-list li").forEach((li) => { if (li.dataset.day === todayName) li.classList.add("today"); });

  /* ---- Footer year ------------------------------------------------------- */
  $$("[data-year]").forEach((el) => (el.textContent = new Date().getFullYear()));

  /* ---- Newsletter (footer) ----------------------------------------------- */
  const news = $("#newsletter-form");
  news?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = news.querySelector("input");
    const btn = news.querySelector("button");
    const original = btn.textContent;
    btn.disabled = true; btn.textContent = "…";
    try {
      const res = await fetch("/api/contact/newsletter", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: input.value }),
      });
      const data = await res.json();
      btn.textContent = res.ok ? "Done ✓" : "Retry";
      if (res.ok) { input.value = ""; input.placeholder = data.message || "You're on the list."; }
    } catch { btn.textContent = "Retry"; }
    setTimeout(() => { btn.disabled = false; btn.textContent = original; }, 2200);
  });
})();
