"use client";

import Image from "next/image";
import { useState } from "react";
import { MoveHorizontal } from "lucide-react";
import { SectionTitle } from "@/components/section-title";
import { Stagger, StaggerItem } from "@/components/motion/reveal";
import { transformations, type Transformation } from "@/lib/data";

function BeforeAfterCard({ item }: { item: Transformation }) {
  const [position, setPosition] = useState(50);

  return (
    <article className="group overflow-hidden rounded-3xl border border-line bg-card transition-all duration-500 hover:border-line-strong hover:-translate-y-1.5 hover:shadow-2xl hover:shadow-black/40">
      {/* Slider */}
      <div className="relative aspect-[4/5] select-none">
        <Image
          src={item.after}
          alt={`${item.name} after the ${item.program} program`}
          fill
          className="object-cover"
          sizes="(min-width: 1024px) 33vw, (min-width: 640px) 50vw, 100vw"
        />
        <div
          className="absolute inset-0 overflow-hidden"
          style={{ clipPath: `inset(0 ${100 - position}% 0 0)` }}
        >
          <Image
            src={item.before}
            alt={`${item.name} before the ${item.program} program`}
            fill
            className="object-cover grayscale"
            sizes="(min-width: 1024px) 33vw, (min-width: 640px) 50vw, 100vw"
          />
        </div>

        {/* Divider handle */}
        <div
          className="pointer-events-none absolute inset-y-0 w-0.5 bg-white/80"
          style={{ left: `${position}%` }}
        >
          <span className="absolute top-1/2 left-1/2 flex size-9 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-white/30 bg-black/60 text-white backdrop-blur-md">
            <MoveHorizontal className="size-4" />
          </span>
        </div>

        <input
          type="range"
          min={0}
          max={100}
          value={position}
          onChange={(e) => setPosition(Number(e.target.value))}
          aria-label={`Compare before and after for ${item.name}`}
          className="absolute inset-0 z-10 size-full cursor-ew-resize opacity-0"
        />

        <span className="absolute top-4 left-4 rounded-full bg-black/60 px-3 py-1 text-[11px] font-semibold tracking-widest text-gray-300 uppercase backdrop-blur-md">
          Before
        </span>
        <span className="absolute top-4 right-4 rounded-full bg-electric/80 px-3 py-1 text-[11px] font-semibold tracking-widest text-white uppercase backdrop-blur-md">
          After
        </span>
      </div>

      {/* Meta */}
      <div className="p-6">
        <div className="flex items-baseline justify-between gap-2">
          <h3 className="text-lg font-semibold tracking-tight text-white">
            {item.name}
          </h3>
          <span className="text-xs font-medium text-gray-500">{item.duration}</span>
        </div>
        <p className="mt-0.5 text-sm text-electric-bright">{item.program}</p>

        <dl className="mt-5 grid grid-cols-3 gap-2 border-t border-line pt-5">
          {item.metrics.map((m) => (
            <div key={m.label}>
              <dd className="text-base font-bold text-emerald">{m.value}</dd>
              <dt className="mt-0.5 text-[11px] tracking-wide text-gray-500 uppercase">
                {m.label}
              </dt>
            </div>
          ))}
        </dl>
      </div>
    </article>
  );
}

export function Transformations() {
  return (
    <section id="transformations" className="mx-auto max-w-7xl scroll-mt-24 px-6 py-24 md:py-36">
      <SectionTitle
        eyebrow="Real Results"
        title="Transformations That Speak for Themselves"
        subtitle="Drag the slider on each card. Every result below is tracked with professional body-composition analysis — verified, not guessed."
      />

      <Stagger className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3" stagger={0.12}>
        {transformations.map((item) => (
          <StaggerItem key={item.name}>
            <BeforeAfterCard item={item} />
          </StaggerItem>
        ))}
      </Stagger>

      <p className="mt-8 text-center text-xs text-gray-600">
        Placeholder imagery shown for mockup purposes. Individual results vary.
      </p>
    </section>
  );
}
