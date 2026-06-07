/* The Queen Victoria — shared site behaviour for every page.
   Each block is guarded by element existence, so the same file powers the
   home page, the menu page, and any future pages. No backend required. */
(function () {
  "use strict";
  var $ = function (s, c) { return (c || document).querySelector(s); };
  var $$ = function (s, c) { return [].slice.call((c || document).querySelectorAll(s)); };
  var reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---- Crest ---- */
  var CREST = '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:100%"><defs><linearGradient id="cg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#E8D49B"/><stop offset="1" stop-color="#C2A04C"/></linearGradient></defs><g fill="none" stroke="url(#cg)" stroke-width="1.6"><path d="M50 8C68 14 80 14 86 12C86 40 82 66 50 92C18 66 14 40 14 12C20 14 32 14 50 8Z"/></g><g fill="url(#cg)"><path d="M34 30 L38 22 L44 28 L50 20 L56 28 L62 22 L66 30 L64 36 L36 36Z"/></g><text x="50" y="62" text-anchor="middle" font-family="Playfair Display,Georgia,serif" font-size="26" font-weight="700" fill="url(#cg)">QV</text></svg>';
  $$("[data-crest]").forEach(function (el) { el.innerHTML = CREST; });

  /* ---- Procedural SVG scene backgrounds ---- */
  var PAL = { hero: { t: "#15402F", b: "#081E18", g: "#E2B85A" }, interior: { t: "#241A12", b: "#0B241D", g: "#E8C07A" }, amber: { t: "#2A1E10", b: "#10342A", g: "#F0C56B" }, wine: { t: "#2A1119", b: "#0A211B", g: "#E8B86A" }, night: { t: "#0E2A22", b: "#06140F", g: "#D9C089" }, sage: { t: "#1C4A3C", b: "#0A211B", g: "#EAD79B" } };
  function rng(s) { return function () { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; }; }
  function scene(w, h, seed, palName, lights, dots) {
    var r = rng(seed), p = PAL[palName] || PAL.hero, id = "z" + seed;
    var s = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + w + ' ' + h + '" preserveAspectRatio="xMidYMid slice">';
    s += '<defs><linearGradient id="b' + id + '" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="' + p.t + '"/><stop offset="1" stop-color="' + p.b + '"/></linearGradient>';
    s += '<radialGradient id="g' + id + '" cx="50%" cy="28%" r="60%"><stop offset="0" stop-color="' + p.g + '" stop-opacity="0.5"/><stop offset="45%" stop-color="' + p.g + '" stop-opacity="0.1"/><stop offset="100%" stop-color="' + p.g + '" stop-opacity="0"/></radialGradient>';
    s += '<radialGradient id="v' + id + '" cx="50%" cy="46%" r="75%"><stop offset="55%" stop-color="#000" stop-opacity="0"/><stop offset="100%" stop-color="#000" stop-opacity="0.55"/></radialGradient>';
    s += '<filter id="s' + id + '"><feGaussianBlur stdDeviation="7"/></filter></defs>';
    s += '<rect width="' + w + '" height="' + h + '" fill="url(#b' + id + ')"/><rect width="' + w + '" height="' + h + '" fill="url(#g' + id + ')"/>';
    for (var i = 0; i < lights; i++) { var x = (w / (lights + 1)) * (i + 1) + (r() - 0.5) * 40, y = h * (0.1 + r() * 0.08); s += '<circle cx="' + x.toFixed(0) + '" cy="' + y.toFixed(0) + '" r="' + (26 + r() * 16).toFixed(0) + '" fill="' + p.g + '" opacity="0.18" filter="url(#s' + id + ')"/><circle cx="' + x.toFixed(0) + '" cy="' + y.toFixed(0) + '" r="5" fill="' + p.g + '" opacity="0.9"/>'; }
    for (var d = 0; d < dots; d++) { var dx = r() * w, dy = h * (0.15 + r() * 0.8), rad = 3 + r() * 20; s += '<circle cx="' + dx.toFixed(0) + '" cy="' + dy.toFixed(0) + '" r="' + rad.toFixed(0) + '" fill="' + p.g + '" opacity="' + (0.04 + r() * 0.1).toFixed(2) + '" filter="url(#s' + id + ')"/>'; }
    var shelfY = h * 0.66; s += '<rect x="0" y="' + shelfY.toFixed(0) + '" width="' + w + '" height="' + (h - shelfY).toFixed(0) + '" fill="#000" opacity="0.32"/>';
    var bx = w * 0.04; while (bx < w * 0.96) { var bw = 14 + r() * 16, bh = 60 + r() * 90, by = shelfY - bh + 10; s += '<rect x="' + bx.toFixed(0) + '" y="' + by.toFixed(0) + '" width="' + bw.toFixed(0) + '" height="' + bh.toFixed(0) + '" rx="' + (bw / 2).toFixed(0) + '" fill="#000" opacity="0.5"/><rect x="' + bx.toFixed(0) + '" y="' + by.toFixed(0) + '" width="2" height="' + bh.toFixed(0) + '" fill="' + p.g + '" opacity="0.35"/>'; bx += bw + 6 + r() * 18; }
    s += '<rect width="' + w + '" height="' + h + '" fill="url(#v' + id + ')"/></svg>';
    return 'url("data:image/svg+xml,' + encodeURIComponent(s) + '")';
  }
  window.qvScene = scene;
  $$("[data-scene]").forEach(function (el) {
    var d = el.dataset;
    el.style.backgroundImage = scene(+(d.w || 1600), +(d.h || 1000), +(d.seed || 1), d.pal || "hero", +(d.lights || 4), +(d.dots || 26));
  });

  /* ---- Gallery (gallery page) ---- */
  var gg = $("#gallery-grid");
  if (gg) {
    [
      ["hero", 11, 1000, "The bar, after dark"],
      ["amber", 22, 700, "Steak & ale, straight from the oven"],
      ["wine", 33, 1100, "The Gin Library"],
      ["interior", 44, 800, "Tuesday quiz night"],
      ["night", 55, 950, "Match day roar"],
      ["sage", 66, 720, "Poured the proper way"],
      ["amber", 77, 880, "Fish & chips, done right"],
      ["interior", 88, 1040, "A corner to call your own"],
      ["hero", 99, 760, "Last orders, never rushed"],
      ["wine", 111, 920, "Sunday roast weather"],
      ["sage", 123, 700, "Forty gins and counting"],
      ["night", 137, 1080, "Where regulars become family"]
    ].forEach(function (t, i) {
      var f = document.createElement("figure"); f.setAttribute("data-reveal", ""); if (i % 2) f.setAttribute("data-delay", "1");
      f.innerHTML = '<div class="scene" style="height:' + (t[2] * 0.42) + 'px;background-image:' + scene(800, t[2], t[1], t[0], 3, 14) + ';background-size:cover"></div><figcaption>' + t[3] + '</figcaption>';
      gg.appendChild(f);
    });
  }

  /* ---- Header / nav ---- */
  var header = $(".site-header"), toggle = $(".nav-toggle"), links = $(".nav-links");
  var solid = header && header.classList.contains("solid");
  function onScroll() { if (header && !solid) header.classList.toggle("scrolled", window.scrollY > 40); }
  onScroll(); addEventListener("scroll", onScroll, { passive: true });
  if (toggle) toggle.addEventListener("click", function () { var o = links.classList.toggle("open"); toggle.classList.toggle("open", o); });
  $$(".nav-links a").forEach(function (a) { a.addEventListener("click", function () { if (links) links.classList.remove("open"); if (toggle) toggle.classList.remove("open"); }); });

  /* ---- Reveal ---- */
  var rv = $$("[data-reveal]");
  if (reduce || !("IntersectionObserver" in window)) { rv.forEach(function (e) { e.classList.add("in"); }); }
  else { var io = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } }); }, { threshold: .12, rootMargin: "0px 0px -8% 0px" }); rv.forEach(function (e) { io.observe(e); }); }

  /* ---- Hero parallax (home) ---- */
  var heroEl = $(".hero .hero-bg");
  if (heroEl && !reduce) { var tk = false; addEventListener("scroll", function () { if (tk) return; tk = true; requestAnimationFrame(function () { var y = Math.min(window.scrollY, innerHeight) * 0.28; heroEl.style.transform = "translate3d(0," + y + "px,0) scale(1.08)"; tk = false; }); }, { passive: true }); }

  /* ---- Counters ---- */
  var cs = $$("[data-count]");
  function animate(el) { var target = parseFloat(el.dataset.count), dec = (el.dataset.count.split(".")[1] || "").length, dur = 1600, start = performance.now(); (function step(now) { var p = Math.min((now - start) / dur, 1), e = 1 - Math.pow(1 - p, 3); el.textContent = (target * e).toFixed(dec) + (el.dataset.suffix || ""); if (p < 1) requestAnimationFrame(step); })(performance.now()); }
  if (cs.length) { if (reduce) { cs.forEach(function (c) { c.textContent = c.dataset.count + (c.dataset.suffix || ""); }); } else { var cio = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) { animate(e.target); cio.unobserve(e.target); } }); }, { threshold: .5 }); cs.forEach(function (c) { cio.observe(c); }); } }

  /* ---- Ticker ---- */
  var tr = $(".ticker-track"); if (tr) tr.innerHTML += tr.innerHTML;

  /* ---- Open-now + today + year ---- */
  var HOURS = { 0: [12, 24], 1: [12, 24], 2: [12, 24], 3: [12, 26], 4: [12, 28], 5: [12, 28], 6: [12, 28] };
  function hk() { var n = new Date(); return new Date(n.getTime() + n.getTimezoneOffset() * 60000 + 8 * 3600000); }
  function openNow() { var n = hk(), m = n.getHours() * 60 + n.getMinutes(), t = HOURS[n.getDay()], y = HOURS[(n.getDay() + 6) % 7]; if (m >= t[0] * 60 && m < t[1] * 60) return true; if (y[1] * 60 > 1440 && m < y[1] * 60 - 1440) return true; return false; }
  $$("[data-open-pill]").forEach(function (p) { var o = openNow(); p.classList.add(o ? "open" : "closed"); p.innerHTML = '<span class="dot"></span>' + (o ? "Open now" : "Currently closed"); });
  var dn = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"][hk().getDay()];
  $$(".hours-list li").forEach(function (li) { if (li.dataset.day === dn) li.classList.add("today"); });
  $$("[data-year]").forEach(function (e) { e.textContent = new Date().getFullYear(); });

  /* ---- Newsletter ---- */
  $$("#newsletter-form, .js-news").forEach(function (form) {
    form.addEventListener("submit", function (e) { e.preventDefault(); var b = form.querySelector("button"), i = form.querySelector("input"); if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(i.value)) return; b.textContent = "Done ✓"; i.value = ""; i.placeholder = "You're on the list. Cheers!"; setTimeout(function () { b.textContent = "Join"; }, 2200); });
  });

  /* ---- Reservations (client-side; on pages that have the form) ---- */
  var resForm = $("#reservation-form");
  if (resForm) {
    var pad = function (n) { return String(n).padStart(2, "0"); }, fmt = function (d) { return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()); };
    var dateI = $("#res-date"), today = new Date(); dateI.min = fmt(today); var mx = new Date(today); mx.setDate(mx.getDate() + 120); dateI.max = fmt(mx); dateI.value = fmt(today);
    var selTime = "", slotsW = $("#res-slots");
    function to12(t) { var a = t.split(":"), h = +a[0], ap = h >= 12 ? "pm" : "am"; h = h % 12 || 12; return h + ":" + a[1] + " " + ap; }
    function buildSlots() { slotsW.innerHTML = ""; selTime = ""; var m = 12 * 60, end = 22 * 60 + 30; while (m <= end) { (function (t) { var b = document.createElement("button"); b.type = "button"; b.className = "slot"; b.textContent = to12(t); b.onclick = function () { $$(".slot", slotsW).forEach(function (x) { x.classList.remove("selected"); }); b.classList.add("selected"); selTime = t; setErr("time", ""); }; slotsW.appendChild(b); })(pad(Math.floor(m / 60)) + ":" + pad(m % 60)); m += 30; } }
    buildSlots();
    function setErr(n, msg) { var f = $('[data-field="' + n + '"]'); if (!f) return; f.classList.toggle("invalid", !!msg); var e = $(".field-error", f); if (e) e.textContent = msg || ""; }
    function ref() { var c = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789", o = ""; for (var i = 0; i < 6; i++) o += c[Math.floor(Math.random() * c.length)]; return o; }
    resForm.addEventListener("submit", function (e) {
      e.preventDefault();
      ["name", "email", "phone", "date", "time"].forEach(function (n) { setErr(n, ""); });
      var name = $("#res-name").value.trim(), email = $("#res-email").value.trim(), phone = $("#res-phone").value.trim(), party = +$("#res-party").value, date = dateI.value, err = false;
      if (name.length < 2) { setErr("name", "Please give us a name."); err = true; }
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { setErr("email", "Enter a valid email."); err = true; }
      if (phone.replace(/\D/g, "").length < 6) { setErr("phone", "Enter a contactable number."); err = true; }
      if (!date) { setErr("date", "Choose a date."); err = true; }
      if (!selTime) { setErr("time", "Please choose a time."); err = true; }
      if (err) return;
      var r = ref(), status = party >= 8 ? "pending" : "confirmed";
      try { var all = JSON.parse(localStorage.getItem("qv_bookings") || "{}"); all[r] = { ref: r, name: name, email: email, phone: phone, party: party, date: date, time: selTime, occasion: $("#res-occasion").value, status: status }; localStorage.setItem("qv_bookings", JSON.stringify(all)); } catch (_) {}
      var nice = new Date(date + "T00:00:00").toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
      $("#confirm-ref").textContent = r;
      $("#confirm-detail").innerHTML = "<strong>" + name + "</strong> · party of " + party + "<br>" + nice + " at " + to12(selTime);
      $("#confirm-message").textContent = status === "pending" ? "Thanks — for a party of " + party + " our team will confirm the details with you by phone or email shortly." : "Your table is booked. We can't wait to welcome you to The Queen Victoria.";
      $("#reservation-view").style.display = "none"; $("#confirmation-view").style.display = "block";
      $("#confirmation-view").scrollIntoView({ behavior: "smooth", block: "center" });
    });
    var again = $("#confirm-again");
    if (again) again.addEventListener("click", function () { resForm.reset(); dateI.value = fmt(today); buildSlots(); $("#confirmation-view").style.display = "none"; $("#reservation-view").style.display = "block"; var rs = $("#reserve"); if (rs) rs.scrollIntoView({ behavior: "smooth", block: "start" }); });
  }

  /* ---- Concierge ---- */
  var R = { phone: "2529 7800", addr: "Floor G, Gaylord Commercial Building, 108 Lockhart Road, Wan Chai, Hong Kong", email: "reservations@thequeenvictoriahk.com", plus: "75HC+5W" };
  function reply(message) {
    var m = (message || "").toLowerCase();
    if (/(happy hour|happyhour|deal|cheap|discount)/.test(m)) return "Our happy hour is one of Wan Chai's best — half-price house pints, wines and selected spirits every weekday from open until 8 pm. 🍺";
    if (/(hour|open|close|time|when.*open)/.test(m)) return "We're open daily from noon. We close at midnight Mon, Tue & Sun, 2 am Wed, and run to 4 am Thu–Sat. 🕛";
    if (/(quiz|trivia)/.test(m)) return "Quiz night is every Tuesday at 8 pm — teams of up to six, free to enter, and the winners take a bar tab. Book a table so you don't miss out.";
    if (/(where|location|address|find|map|mtr|getting)/.test(m)) return "You'll find us at " + R.addr + ". About five minutes from Wan Chai MTR (Exit A3). Plus code " + R.plus + ".";
    if (/(book|reserv|table)/.test(m)) return "Happy to help! Head to the Reserve page to book a table, or call us on " + R.phone + ". For groups of 8+ we'll confirm the details personally.";
    if (/(pie)/.test(m)) return "The pies are our pride and joy — all-butter pastry and proper gravy. The Steak & Ale Pie (HK$168) is the one we're known for. 🥧";
    if (/(fish|chips)/.test(m)) return "Our Fish & Chips (HK$178) is beer-battered North Atlantic cod with triple-cooked chips, mushy peas and tartare.";
    if (/(burger)/.test(m)) return "The Queen Vic Burger (HK$158) — two smashed beef patties, cheddar, bacon, house sauce and fries. There's a buttermilk chicken and a Beyond version too.";
    if (/(veg|vegan|vegetarian|plant)/.test(m)) return "Plenty for you — wild mushroom & spinach pie, halloumi fries, the Beyond Burger, mac & cheese and more. Flag any allergies and the kitchen will guide you.";
    if (/(gin|cocktail|drink|beer|ale|wine|guinness)/.test(m)) return "The bar's the heart of the place: hand-pulled ales, a properly poured Guinness, over forty gins in our Gin Library, and classics like a Pimm's or Espresso Martini.";
    if (/(menu|eat|food|dish|serve)/.test(m)) return "We serve British pub classics all day — pies, fish & chips, bangers & mash, burgers, all-day breakfast and puddings like sticky toffee. See the Menu page for the full list. What are you in the mood for?";
    if (/(event|private|party|birthday|function|corporate)/.test(m)) return "We'd love to host you — birthdays, corporate drinks, leaving dos and watch parties. Email " + R.email + " or call " + R.phone + ".";
    if (/(dog|pet)/.test(m)) return "Well-behaved dogs are very welcome in the bar. 🐾";
    if (/(sport|football|rugby|match|premier|game)/.test(m)) return "We show all the big fixtures — Premier League, rugby, the Six Nations and more — across our screens. Pop in or call to check what's on.";
    if (/(deliver|takeaway|take away|pick up)/.test(m)) return "Yes — the full menu is available for dine-in, takeaway and delivery around Wan Chai.";
    if (/(hello|hi|hey|good (morning|afternoon|evening))/.test(m)) return "Hello and welcome to The Queen Victoria! 🍺 I can help with our menu, opening hours, happy hour, the quiz, bookings and finding us. What can I get you?";
    if (/(thank|cheers)/.test(m)) return "My pleasure — cheers! Anything else I can help with?";
    return "I can tell you about our menu, opening hours, happy hour, quiz night, private events and how to find us — or help you book a table. For anything specific, call us on " + R.phone + ". What would you like to know?";
  }
  var cfab = $("#concierge-fab"), croot = $("#concierge");
  if (cfab && croot) {
    var cbody = $(".concierge-body", croot), greeted = false;
    function esc(s) { return s.replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
    function fmtMsg(t) { return esc(t).replace(/\b(\d{4}\s?\d{4})\b/g, '<a href="tel:+852$1">$1</a>').replace(/\b([\w.+-]+@[\w-]+\.[\w.-]+)\b/g, '<a href="mailto:$1">$1</a>'); }
    function addMsg(role, text) { var el = document.createElement("div"); el.className = "msg " + role; el.innerHTML = fmtMsg(text); cbody.appendChild(el); cbody.scrollTop = cbody.scrollHeight; return el; }
    function openC() { croot.classList.add("open"); cfab.style.display = "none"; if (!greeted) { greeted = true; addMsg("bot", "Welcome to The Queen Victoria! 🍺 I'm your concierge. Ask me about our menu, opening hours, happy hour, the quiz — or how to book a table."); } setTimeout(function () { $("input", croot).focus(); }, 300); }
    function closeC() { croot.classList.remove("open"); cfab.style.display = "grid"; }
    cfab.addEventListener("click", openC); $(".concierge-close", croot).addEventListener("click", closeC);
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && croot.classList.contains("open")) closeC(); });
    function ask(message) {
      if (!message.trim()) return; addMsg("user", message);
      var typing = document.createElement("div"); typing.className = "concierge-typing"; typing.innerHTML = "<span></span><span></span><span></span>"; cbody.appendChild(typing); cbody.scrollTop = cbody.scrollHeight;
      var ans = reply(message);
      setTimeout(function () { typing.remove(); var el = addMsg("bot", ""); var words = ans.split(/(\s+)/), i = 0; (function tick() { if (i < words.length) { el.innerHTML = fmtMsg(words.slice(0, ++i).join("")); cbody.scrollTop = cbody.scrollHeight; setTimeout(tick, 18); } })(); }, 550);
    }
    $("#cform", croot).addEventListener("submit", function (e) { e.preventDefault(); var i = $("input", e.target); ask(i.value); i.value = ""; });
    var sug = $(".concierge-suggest", croot); if (sug) sug.addEventListener("click", function (e) { var b = e.target.closest("button"); if (b) { openC(); ask(b.textContent); } });
    window.askConcierge = function (q) { openC(); if (q) ask(q); };
  }
})();
