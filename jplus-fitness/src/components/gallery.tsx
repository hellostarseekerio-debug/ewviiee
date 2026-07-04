"use client";

import Image from "next/image";
import { Expand } from "lucide-react";
import { SectionTitle } from "@/components/section-title";
import { Stagger, StaggerItem } from "@/components/motion/reveal";
import { galleryImages } from "@/lib/data";
import { cn } from "@/lib/utils";

export function Gallery() {
  return (
    <section id="gallery" className="mx-auto max-w-7xl scroll-mt-24 px-6 py-24 md:py-36">
      <SectionTitle
        eyebrow="The Studio"
        title="A Space Designed for Focus"
        subtitle="Premium equipment, immaculate facilities and a private atmosphere in the heart of Central."
      />

      <Stagger
        className="columns-1 gap-5 space-y-5 sm:columns-2 lg:columns-3"
        stagger={0.07}
      >
        {galleryImages.map((image) => (
          <StaggerItem key={image.src} className="break-inside-avoid">
            <figure
              className={cn(
                "group relative cursor-zoom-in overflow-hidden rounded-3xl border border-line",
                image.tall ? "aspect-[3/4]" : "aspect-[4/3]"
              )}
            >
              <Image
                src={image.src}
                alt={image.alt}
                fill
                className="object-cover transition-transform duration-700 group-hover:scale-110"
                sizes="(min-width: 1024px) 33vw, (min-width: 640px) 50vw, 100vw"
              />
              {/* Lightbox-style hover overlay (visual only) */}
              <div className="absolute inset-0 flex items-end justify-between bg-gradient-to-t from-black/70 via-transparent p-5 opacity-0 transition-opacity duration-500 group-hover:opacity-100">
                <figcaption className="max-w-[75%] text-sm font-medium text-white">
                  {image.alt}
                </figcaption>
                <span className="glass-bright flex size-10 items-center justify-center rounded-full text-white">
                  <Expand className="size-4" />
                </span>
              </div>
            </figure>
          </StaggerItem>
        ))}
      </Stagger>
    </section>
  );
}
