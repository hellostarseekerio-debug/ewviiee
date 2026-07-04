"use client";

import Image from "next/image";
import { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronLeft, ChevronRight, Star } from "lucide-react";
import { SectionTitle } from "@/components/section-title";
import { Reveal } from "@/components/motion/reveal";
import { testimonials } from "@/lib/data";
import { cn } from "@/lib/utils";

const VISIBLE = 3;

export function Testimonials() {
  const [page, setPage] = useState(0);
  const [direction, setDirection] = useState(1);
  const pages = Math.ceil(testimonials.length / VISIBLE);

  const go = useCallback(
    (dir: number) => {
      setDirection(dir);
      setPage((p) => (p + dir + pages) % pages);
    },
    [pages]
  );

  useEffect(() => {
    const id = setInterval(() => go(1), 8000);
    return () => clearInterval(id);
  }, [go]);

  const slice = testimonials.slice(page * VISIBLE, page * VISIBLE + VISIBLE);

  return (
    <section id="reviews" className="relative scroll-mt-24 overflow-hidden py-24 md:py-36">
      <div className="pointer-events-none absolute top-1/3 left-1/2 -z-10 h-[420px] w-[820px] -translate-x-1/2 rounded-full bg-emerald/8 blur-[160px]" />

      <div className="mx-auto max-w-7xl px-6">
        <SectionTitle
          eyebrow="Client Reviews"
          title="Loved by Clients Across Hong Kong"
          subtitle="Real words from real members — inspired by our 5.0-star Google reviews."
        />

        <div className="relative">
          <AnimatePresence mode="wait" custom={direction}>
            <motion.ul
              key={page}
              custom={direction}
              initial={{ opacity: 0, x: direction * 60 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: direction * -60 }}
              transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
              className="grid gap-6 md:grid-cols-3"
            >
              {slice.map((t) => (
                <li key={t.name}>
                  <figure className="glass flex h-full flex-col rounded-3xl p-7 transition-all duration-300 hover:-translate-y-1 hover:border-line-strong">
                    <div className="flex items-center justify-between">
                      <div className="flex gap-1" aria-label={`${t.rating} out of 5 stars`}>
                        {Array.from({ length: t.rating }).map((_, i) => (
                          <Star key={i} className="size-4 fill-emerald text-emerald" />
                        ))}
                      </div>
                      <span className="rounded-full bg-electric/10 px-3 py-1 text-[11px] font-medium text-electric-bright">
                        {t.tag}
                      </span>
                    </div>

                    <blockquote className="mt-5 flex-1 text-sm leading-relaxed text-gray-300">
                      &ldquo;{t.quote}&rdquo;
                    </blockquote>

                    <figcaption className="mt-6 flex items-center gap-3 border-t border-line pt-5">
                      <Image
                        src={t.avatar}
                        alt=""
                        width={40}
                        height={40}
                        className="size-10 rounded-full object-cover"
                      />
                      <div>
                        <p className="text-sm font-semibold text-white">{t.name}</p>
                        <p className="text-xs text-gray-500">{t.meta}</p>
                      </div>
                    </figcaption>
                  </figure>
                </li>
              ))}
            </motion.ul>
          </AnimatePresence>

          {/* Controls */}
          <Reveal delay={0.2} className="mt-10 flex items-center justify-center gap-4">
            <button
              type="button"
              onClick={() => go(-1)}
              aria-label="Previous reviews"
              className="glass-bright flex size-11 cursor-pointer items-center justify-center rounded-full text-gray-300 transition-all duration-300 hover:bg-white/10 hover:text-white"
            >
              <ChevronLeft className="size-5" />
            </button>
            <div className="flex gap-2">
              {Array.from({ length: pages }).map((_, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => {
                    setDirection(i > page ? 1 : -1);
                    setPage(i);
                  }}
                  aria-label={`Go to review page ${i + 1}`}
                  className={cn(
                    "h-1.5 cursor-pointer rounded-full transition-all duration-300",
                    i === page ? "w-8 bg-electric" : "w-3 bg-white/15 hover:bg-white/30"
                  )}
                />
              ))}
            </div>
            <button
              type="button"
              onClick={() => go(1)}
              aria-label="Next reviews"
              className="glass-bright flex size-11 cursor-pointer items-center justify-center rounded-full text-gray-300 transition-all duration-300 hover:bg-white/10 hover:text-white"
            >
              <ChevronRight className="size-5" />
            </button>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
