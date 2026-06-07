/* Full menu data + rendering with dietary filters. Runs only on pages that
   include #menu-content (the Menu page). */
(function () {
  "use strict";
  var mc = document.getElementById("menu-content");
  if (!mc) return;
  var mf = document.getElementById("menu-filters");

  var MENU = {
    tagLabels: { v: "Vegetarian", ve: "Vegan", gf: "Gluten-free option", spicy: "Spicy", signature: "Signature" },
    categories: [
      { id: "starters", name: "Starters & Sharers", desc: "To begin, or to graze across the table over a pint.", items: [
        { n: "Scotch Egg", p: 78, d: "Free-range egg wrapped in seasoned pork, breadcrumbed and fried, English mustard mayo.", t: ["signature"] },
        { n: "Chicken Wings", p: 88, d: "A pound of wings tossed in buffalo, BBQ or salt & pepper, blue cheese dip.", t: ["spicy", "signature"] },
        { n: "Loaded Skin-On Fries", p: 92, d: "Cheddar, smoked bacon, spring onion and burnt-end gravy.", t: [] },
        { n: "Soup of the Day", p: 68, d: "Made fresh each morning, served with a warm bread roll and butter.", t: ["v"] },
        { n: "Halloumi Fries", p: 82, d: "Golden fried halloumi, harissa honey, lemon.", t: ["v"] },
        { n: "Nachos Royale", p: 98, d: "Tortillas piled with cheese, jalapeños, salsa, guacamole and sour cream.", t: ["v", "spicy"] },
        { n: "Pork Pie", p: 72, d: "Hand-raised, served with piccalilli.", t: [] } ] },
      { id: "pies", name: "The Pie Counter", desc: "Our pride and joy. All-butter pastry, proper gravy, served with mash or chips and seasonal veg.", items: [
        { n: "Steak & Ale Pie", p: 168, d: "Slow-braised beef in our house ale gravy. The one we're known for.", t: ["signature"] },
        { n: "Chicken & Leek Pie", p: 158, d: "Free-range chicken, leeks and tarragon in a creamy sauce.", t: [] },
        { n: "Steak & Kidney Pie", p: 168, d: "The proper old-school filling, rich and unapologetic.", t: [] },
        { n: "Wild Mushroom & Spinach Pie", p: 148, d: "Wild mushrooms, spinach and thyme in a white wine cream.", t: ["v"] },
        { n: "Pie of the Day", p: 162, d: "Ask the bar — when it's gone, it's gone.", t: ["signature"] } ] },
      { id: "classics", name: "Pub Classics", desc: "The dishes that built the place.", items: [
        { n: "Fish & Chips", p: 178, d: "Beer-battered North Atlantic cod, triple-cooked chips, mushy peas, tartare.", t: ["signature"] },
        { n: "Bangers & Mash", p: 148, d: "Award-winning Cumberland sausages, buttery mash, onion gravy.", t: [] },
        { n: "Sausage, Mash & Baked Beans", p: 138, d: "A house favourite — proper comfort on a plate.", t: ["signature"] },
        { n: "The Queen Vic Burger", p: 158, d: "Two smashed beef patties, cheddar, bacon, house sauce, brioche, fries.", t: ["signature"] },
        { n: "Buttermilk Chicken Burger", p: 148, d: "Crispy buttermilk chicken thigh, slaw, sriracha mayo, fries.", t: ["spicy"] },
        { n: "Beyond Burger", p: 152, d: "Plant-based patty, vegan cheese, smoked tomato relish, fries.", t: ["ve"] },
        { n: "Spicy Omelette", p: 118, d: "Three-egg omelette with chilli, onion and cheese — a cult favourite.", t: ["v", "spicy", "signature"] },
        { n: "Ploughman's Board", p: 168, d: "Mature cheddar, ham, pork pie, pickles, chutney and crusty bread.", t: [] } ] },
      { id: "breakfast", name: "All-Day Breakfast", desc: "Served from open to close, because some days call for it.", items: [
        { n: "The Full English", p: 158, d: "Sausage, bacon, fried eggs, beans, grilled tomato, mushrooms, hash brown and toast.", t: ["signature"] },
        { n: "Veggie Breakfast", p: 138, d: "All the trimmings, meat-free, with halloumi.", t: ["v"] },
        { n: "Eggs Benedict", p: 128, d: "Poached eggs, ham, hollandaise on a toasted muffin.", t: [] },
        { n: "Smashed Avocado on Sourdough", p: 118, d: "Chilli, lime, poached egg, dukkah.", t: ["v"] } ] },
      { id: "sides", name: "Sides", items: [
        { n: "Triple-Cooked Chips", p: 52, d: "Crisp outside, fluffy in.", t: ["v", "ve"] },
        { n: "Skin-On Fries", p: 48, d: "", t: ["v", "ve"] },
        { n: "Garden Salad", p: 48, d: "House dressing.", t: ["v", "ve", "gf"] },
        { n: "Beer-Battered Onion Rings", p: 52, d: "", t: ["v"] },
        { n: "Buttered Seasonal Greens", p: 48, d: "", t: ["v", "gf"] },
        { n: "Mac & Cheese", p: 78, d: "Three-cheese, crispy crumb.", t: ["v"] } ] },
      { id: "puddings", name: "Puddings", items: [
        { n: "Sticky Toffee Pudding", p: 88, d: "Warm date sponge, toffee sauce, vanilla ice cream.", t: ["v", "signature"] },
        { n: "Eton Mess", p: 82, d: "Crushed meringue, cream, seasonal berries.", t: ["v", "gf"] },
        { n: "Apple & Berry Crumble", p: 82, d: "With proper custard.", t: ["v"] },
        { n: "Cheese Board", p: 118, d: "Three British cheeses, crackers, quince, grapes.", t: ["v"] } ] },
      { id: "draught", name: "On Draught", desc: "Hand-pulled and ice-cold. Ask about this week's guest ale.", items: [
        { n: "London Pride", p: 78, d: "Pint of the classic English bitter.", t: [] },
        { n: "Guinness", p: 82, d: "Poured properly, the two-part way.", t: ["signature"] },
        { n: "Camden Hells Lager", p: 78, d: "Crisp and clean.", t: [] },
        { n: "Guest Ale", p: 80, d: "Rotating cask — ask the bar.", t: [] },
        { n: "Strongbow Cider", p: 76, d: "", t: ["gf"] } ] },
      { id: "gin", name: "The Gin Library", desc: "Over forty gins, each served with the right tonic and garnish.", items: [
        { n: "Hendrick's & Tonic", p: 98, d: "Cucumber, Mediterranean tonic.", t: ["signature"] },
        { n: "Tanqueray No. Ten", p: 102, d: "Grapefruit, premium tonic.", t: [] },
        { n: "Perfumer's Hong Kong Dry Gin", p: 108, d: "Local craft, citrus and lemongrass.", t: ["signature"] },
        { n: "Monkey 47", p: 128, d: "47 botanicals, Black Forest.", t: [] },
        { n: "Sloe Gin Royale", p: 98, d: "Topped with sparkling wine.", t: [] } ] },
      { id: "cocktails", name: "Cocktails & Wine", items: [
        { n: "Pimm's No. 1 Cup", p: 98, d: "Summer in a glass — fruit, mint, lemonade.", t: ["signature"] },
        { n: "Espresso Martini", p: 108, d: "Vodka, coffee liqueur, fresh espresso.", t: [] },
        { n: "Negroni", p: 102, d: "Equal parts, orange peel.", t: [] },
        { n: "Aperol Spritz", p: 98, d: "Prosecco, soda, Aperol.", t: [] },
        { n: "House Red / White / Rosé", p: 78, d: "By the glass. Ask for the bottle list.", t: [] },
        { n: "Prosecco", p: 88, d: "By the glass.", t: [] } ] },
      { id: "soft", name: "Soft & Hot", items: [
        { n: "Soft Drinks", p: 38, d: "Coke, Diet Coke, lemonade, ginger ale, juices.", t: ["ve", "gf"] },
        { n: "Fever-Tree Tonics", p: 42, d: "Indian, Mediterranean, elderflower.", t: ["ve", "gf"] },
        { n: "English Breakfast Tea", p: 38, d: "Pot for one.", t: ["v", "gf"] },
        { n: "Coffee", p: 42, d: "Espresso, flat white, cappuccino, americano.", t: ["v"] } ] }
    ]
  };

  var activeTag = "all";
  function tagMk(ts) { return ts.map(function (t) { return '<span class="tag ' + (t === "signature" ? "tag--signature" : "") + '">' + (MENU.tagLabels[t] || t) + "</span>"; }).join(""); }
  function render() {
    mc.innerHTML = MENU.categories.map(function (c) {
      var items = c.items.filter(function (i) { return activeTag === "all" || i.t.indexOf(activeTag) > -1; }).map(function (i) {
        return '<div class="menu-item"><span class="menu-item-name">' + i.n + " " + tagMk(i.t) + '</span><span class="menu-item-price">$' + i.p + "</span>" + (i.d ? '<span class="menu-item-desc">' + i.d + "</span>" : "") + "</div>";
      }).join("");
      if (!items) return "";
      return '<div class="menu-cat" id="cat-' + c.id + '"><div class="menu-cat-head"><h3>' + c.name + '</h3><span class="rule"></span></div>' + (c.desc ? '<p class="muted mb-2">' + c.desc + "</p>" : "") + items + "</div>";
    }).join("") || '<p class="muted center">No dishes match that filter.</p>';
  }
  if (mf) {
    ["all", "signature", "v", "ve", "gf", "spicy"].forEach(function (t) {
      var b = document.createElement("button"); b.className = "filter-btn" + (t === "all" ? " active" : ""); b.textContent = t === "all" ? "Everything" : (MENU.tagLabels[t] || t);
      b.onclick = function () { activeTag = t; [].slice.call(mf.querySelectorAll(".filter-btn")).forEach(function (x) { x.classList.toggle("active", x === b); }); render(); };
      mf.appendChild(b);
    });
  }
  render();
})();
