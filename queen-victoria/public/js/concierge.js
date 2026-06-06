/* The Queen Victoria AI Concierge — chat widget with live SSE streaming. */
(() => {
  "use strict";
  const root = document.getElementById("concierge");
  const fab = document.getElementById("concierge-fab");
  if (!root || !fab) return;

  const body = root.querySelector(".concierge-body");
  const form = root.querySelector(".concierge-input");
  const input = form.querySelector("input");
  const sendBtn = form.querySelector("button");
  const suggestWrap = root.querySelector(".concierge-suggest");
  const closeBtn = root.querySelector(".concierge-close");

  const history = [];
  let streaming = false;
  let greeted = false;

  const scrollDown = () => { body.scrollTop = body.scrollHeight; };

  // Minimal, safe rich text: escape HTML, then linkify bare URLs & emails.
  const escapeHtml = (s) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const format = (text) => {
    let t = escapeHtml(text);
    t = t.replace(/\bhttps?:\/\/[^\s<]+/g, (u) => `<a href="${u}" target="_blank" rel="noopener">${u}</a>`);
    t = t.replace(/\b([\w.+-]+@[\w-]+\.[\w.-]+)\b/g, '<a href="mailto:$1">$1</a>');
    t = t.replace(/\b(\d{4}\s?\d{4})\b/g, '<a href="tel:+852$1">$1</a>');
    return t.replace(/\n/g, "<br>");
  };

  const addMsg = (role, text = "") => {
    const el = document.createElement("div");
    el.className = `msg ${role}`;
    el.innerHTML = format(text);
    body.appendChild(el);
    scrollDown();
    return el;
  };

  const showTyping = () => {
    const t = document.createElement("div");
    t.className = "concierge-typing";
    t.innerHTML = "<span></span><span></span><span></span>";
    body.appendChild(t);
    scrollDown();
    return t;
  };

  const open = () => {
    root.classList.add("open");
    fab.style.display = "none";
    if (!greeted) {
      greeted = true;
      addMsg("bot", "Welcome to The Queen Victoria! 🍺 I'm your concierge. Ask me about our menu, opening hours, happy hour, the Tuesday quiz, private events — or how to book a table.");
    }
    setTimeout(() => input.focus(), 300);
  };
  const close = () => { root.classList.remove("open"); fab.style.display = "grid"; };

  fab.addEventListener("click", open);
  closeBtn.addEventListener("click", close);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && root.classList.contains("open")) close(); });

  async function ask(message) {
    if (streaming || !message.trim()) return;
    streaming = true;
    sendBtn.disabled = true;
    input.value = "";
    suggestWrap?.remove();

    addMsg("user", message);
    history.push({ role: "user", content: message });
    const typing = showTyping();

    let botEl = null;
    let full = "";
    const ensureBot = () => { if (!botEl) { typing.remove(); botEl = addMsg("bot"); } };

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, history: history.slice(0, -1) }),
      });

      if (!res.ok || !res.body) {
        const data = await res.json().catch(() => ({}));
        ensureBot();
        botEl.innerHTML = format(data.error || "Apologies — I'm momentarily unavailable. Please call us on 2529 7800.");
        return;
      }

      // Parse the Server-Sent Events stream.
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split("\n\n");
        buffer = chunks.pop();
        for (const chunk of chunks) {
          const ev = /event:\s*(.+)/.exec(chunk)?.[1];
          const dataLine = /data:\s*(.+)/.exec(chunk)?.[1];
          if (!dataLine) continue;
          const payload = JSON.parse(dataLine);
          if (ev === "delta") {
            ensureBot();
            full += payload.text;
            botEl.innerHTML = format(full);
            scrollDown();
          } else if (ev === "done") {
            ensureBot();
            if (payload.text) full = payload.text;
            botEl.innerHTML = format(full);
          }
        }
      }
      if (!botEl) { typing.remove(); botEl = addMsg("bot", "Sorry, I didn't catch that. Could you rephrase?"); full = botEl.textContent; }
      history.push({ role: "assistant", content: full });
    } catch (err) {
      ensureBot();
      botEl.innerHTML = format("Apologies — something went wrong. Please call us on 2529 7800 or try again.");
    } finally {
      streaming = false;
      sendBtn.disabled = false;
      scrollDown();
    }
  }

  form.addEventListener("submit", (e) => { e.preventDefault(); ask(input.value); });
  suggestWrap?.addEventListener("click", (e) => {
    const btn = e.target.closest("button");
    if (btn) { open(); ask(btn.textContent); }
  });

  // Allow other parts of the site to open the concierge with a question.
  window.askConcierge = (q) => { open(); if (q) ask(q); };
})();
