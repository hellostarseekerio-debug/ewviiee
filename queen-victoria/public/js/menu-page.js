/* Menu page: fetch the live menu from the API, render it, and filter by
   category and dietary tag. */
(() => {
  "use strict";
  const wrap = document.getElementById("menu-content");
  const catNav = document.getElementById("menu-cats");
  const filterWrap = document.getElementById("menu-filters");
  if (!wrap) return;

  let data = null;
  let activeTag = "all";

  const tagMarkup = (tags, labels) =>
    tags.map((t) => `<span class="tag ${t === "signature" ? "tag--signature" : ""}">${labels[t] || t}</span>`).join("");

  function render() {
    const cats = data.categories
      .map((c) => {
        const items = c.items
          .filter((i) => activeTag === "all" || i.tags.includes(activeTag))
          .map(
            (i) => `
            <div class="menu-item" data-reveal>
              <span class="menu-item-name">${i.name} ${tagMarkup(i.tags, data.tagLabels)}</span>
              <span class="menu-item-price">$${i.price}</span>
              ${i.description ? `<span class="menu-item-desc">${i.description}</span>` : ""}
            </div>`
          )
          .join("");
        if (!items) return "";
        return `
          <div class="menu-cat" id="cat-${c.id}">
            <div class="menu-cat-head">
              <h3>${c.name}</h3><span class="rule"></span>
            </div>
            ${c.description ? `<p class="muted mb-2">${c.description}</p>` : ""}
            ${items}
          </div>`;
      })
      .join("");
    wrap.innerHTML = cats || '<p class="muted center">No dishes match that filter.</p>';
    // Re-trigger reveal for freshly rendered items.
    wrap.querySelectorAll("[data-reveal]").forEach((el, i) => {
      setTimeout(() => el.classList.add("in"), Math.min(i * 25, 400));
    });
  }

  function buildControls() {
    // Category quick-jump.
    if (catNav) {
      catNav.innerHTML = data.categories
        .map((c) => `<a href="#cat-${c.id}" class="filter-btn">${c.name}</a>`)
        .join("");
    }
    // Dietary filters.
    if (filterWrap) {
      const tags = ["all", "signature", "v", "ve", "gf", "spicy"];
      filterWrap.innerHTML = tags
        .map((t) => `<button class="filter-btn ${t === "all" ? "active" : ""}" data-tag="${t}">${t === "all" ? "Everything" : data.tagLabels[t] || t}</button>`)
        .join("");
      filterWrap.addEventListener("click", (e) => {
        const btn = e.target.closest("[data-tag]");
        if (!btn) return;
        activeTag = btn.dataset.tag;
        filterWrap.querySelectorAll(".filter-btn").forEach((b) => b.classList.toggle("active", b === btn));
        render();
      });
    }
  }

  fetch("/api/menu")
    .then((r) => r.json())
    .then((d) => { data = d; buildControls(); render(); })
    .catch(() => { wrap.innerHTML = '<p class="muted center">Our menu is briefly unavailable. Please call us on 2529 7800.</p>'; });
})();
