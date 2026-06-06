import { Router } from "express";
import { menu, tagLabels } from "../data/menu.js";

const router = Router();

// GET /api/menu — full menu, optionally filtered by dietary tag or category.
router.get("/", (req, res) => {
  const tag = typeof req.query.tag === "string" ? req.query.tag : null;
  const categoryId = typeof req.query.category === "string" ? req.query.category : null;

  let categories = menu.categories;
  if (categoryId) categories = categories.filter((c) => c.id === categoryId);
  if (tag) {
    categories = categories
      .map((c) => ({ ...c, items: c.items.filter((i) => i.tags.includes(tag)) }))
      .filter((c) => c.items.length > 0);
  }

  res.json({ ok: true, currency: menu.currency, note: menu.note, tagLabels, categories });
});

export default router;
