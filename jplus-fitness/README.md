# J Plus Fitness — Marketing Website Mockup

An ultra-premium marketing website mockup for **J Plus Fitness Co Ltd**, a
high-end personal training studio at 6/F Abdoolally House, 20 Stanley Street,
Central, Hong Kong.

> **Note:** This is a designed frontend mockup only. Buttons, forms, booking
> and contact functionality are intentionally non-functional and all content
> uses placeholder data and imagery.

## Tech Stack

- [Next.js 15](https://nextjs.org) (App Router) + React 19
- TypeScript
- Tailwind CSS v4
- Framer Motion
- Lucide Icons
- Dark mode by default

## Getting Started

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

> Placeholder imagery is served from `images.unsplash.com`, so an internet
> connection is required for photos to display.

## Structure

```
src/
├── app/                  # App Router entry (layout, page, global styles)
├── components/
│   ├── motion/           # Reusable Framer Motion helpers (Reveal, Stagger, Counter)
│   ├── ui/               # UI primitives (Button, Badge)
│   └── *.tsx             # Page sections (Hero, Services, Pricing, ...)
└── lib/
    ├── data.ts           # All placeholder content in one place
    └── utils.ts          # cn() class helper
```

## Page Sections

Floating glass navbar · Full-screen hero with parallax + animated stats ·
Trust/review marquee · About · Services · Before/after transformation sliders ·
Coach profiles · Animated training-process timeline · Testimonial carousel ·
Pricing · Masonry facility gallery · FAQ accordion · CTA banner · Contact ·
Footer.
