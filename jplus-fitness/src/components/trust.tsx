"use client";

import { Star } from "lucide-react";
import { Reveal } from "@/components/motion/reveal";
import { reviewHighlights } from "@/lib/data";

export function Trust() {
  const marqueeItems = [...reviewHighlights, ...reviewHighlights];

  return (
    <section aria-label="Client trust" className="relative border-y border-line py-16 md:py-20">
      <div className="mx-auto max-w-7xl px-6">
        <Reveal className="flex flex-col items-center gap-5 text-center">
          <div className="flex items-center gap-1.5">
            {Array.from({ length: 5 }).map((_, i) => (
              <Star
                key={i}
                className="size-6 fill-emerald text-emerald md:size-7"
              />
            ))}
          </div>
          <p className="text-2xl font-semibold tracking-tight text-white md:text-3xl">
            27+ Five-Star Reviews on Google
          </p>
          <p className="max-w-xl text-sm leading-relaxed text-gray-400 md:text-base">
            A perfect 5.0 rating, earned one transformation at a time — from
            first-time trainees to competitive athletes across Hong Kong.
          </p>
        </Reveal>
      </div>

      {/* Highlight marquee */}
      <Reveal delay={0.2} className="mt-12 overflow-hidden" y={0}>
        <div
          className="flex w-max animate-marquee gap-3 pr-3"
          style={{
            maskImage:
              "linear-gradient(90deg, transparent, black 12%, black 88%, transparent)",
            WebkitMaskImage:
              "linear-gradient(90deg, transparent, black 12%, black 88%, transparent)",
          }}
        >
          {marqueeItems.map((item, i) => (
            <span
              key={`${item}-${i}`}
              className="glass-bright flex items-center gap-2 rounded-full px-5 py-2.5 text-sm whitespace-nowrap text-gray-300"
            >
              <Star className="size-3.5 fill-emerald text-emerald" />
              {item}
            </span>
          ))}
        </div>
      </Reveal>
    </section>
  );
}
