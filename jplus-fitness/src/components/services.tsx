"use client";

import { ArrowUpRight } from "lucide-react";
import { SectionTitle } from "@/components/section-title";
import { Stagger, StaggerItem } from "@/components/motion/reveal";
import { services } from "@/lib/data";
import { cn } from "@/lib/utils";

export function Services() {
  return (
    <section id="services" className="relative scroll-mt-24 py-24 md:py-36">
      <div className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-full grid-fade" />
      <div className="mx-auto max-w-7xl px-6">
        <SectionTitle
          eyebrow="What We Do"
          title="Precision Programs for Every Goal"
          subtitle="Six core disciplines, one standard: measurable results delivered through elite one-on-one coaching."
        />

        <Stagger className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3" stagger={0.08}>
          {services.map((service) => (
            <StaggerItem key={service.title}>
              <article className="group relative h-full overflow-hidden rounded-3xl border border-line bg-card p-7 transition-all duration-500 hover:border-line-strong hover:bg-card-hover hover:-translate-y-1.5 hover:shadow-2xl hover:shadow-black/40">
                {/* Hover glow */}
                <div
                  className={cn(
                    "pointer-events-none absolute -top-24 -right-24 size-48 rounded-full opacity-0 blur-[80px] transition-opacity duration-700 group-hover:opacity-100",
                    service.accent === "electric" ? "bg-electric/30" : "bg-emerald/25"
                  )}
                />
                <div className="flex items-start justify-between">
                  <span
                    className={cn(
                      "flex size-12 items-center justify-center rounded-2xl transition-transform duration-500 group-hover:scale-110",
                      service.accent === "electric"
                        ? "bg-electric/10 text-electric-bright"
                        : "bg-emerald/10 text-emerald"
                    )}
                  >
                    <service.icon className="size-6" />
                  </span>
                  <ArrowUpRight className="size-5 text-gray-600 transition-all duration-300 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-white" />
                </div>
                <h3 className="mt-6 text-lg font-semibold tracking-tight text-white">
                  {service.title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-gray-400">
                  {service.description}
                </p>
              </article>
            </StaggerItem>
          ))}
        </Stagger>
      </div>
    </section>
  );
}
