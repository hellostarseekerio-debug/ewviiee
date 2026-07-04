"use client";

import { Check, Sparkles } from "lucide-react";
import { SectionTitle } from "@/components/section-title";
import { Stagger, StaggerItem } from "@/components/motion/reveal";
import { Button } from "@/components/ui/button";
import { plans } from "@/lib/data";
import { cn } from "@/lib/utils";

export function Pricing() {
  return (
    <section id="pricing" className="relative scroll-mt-24 border-y border-line bg-card/40 py-24 md:py-36">
      <div className="mx-auto max-w-7xl px-6">
        <SectionTitle
          eyebrow="Membership"
          title="Invest in the Only Body You'll Ever Own"
          subtitle="Transparent monthly programs. No joining fees, no lock-in contracts — just coaching that delivers."
        />

        <Stagger
          className="mx-auto grid max-w-5xl items-stretch gap-6 lg:grid-cols-3"
          stagger={0.12}
        >
          {plans.map((plan) => (
            <StaggerItem key={plan.name} className="h-full">
              <article
                className={cn(
                  "relative flex h-full flex-col rounded-3xl border p-8 transition-all duration-500 hover:-translate-y-2",
                  plan.highlighted
                    ? "ring-glow border-electric/50 bg-card lg:scale-[1.04]"
                    : "border-line bg-card hover:border-line-strong"
                )}
              >
                {plan.highlighted && (
                  <span className="absolute -top-3.5 left-1/2 flex -translate-x-1/2 items-center gap-1.5 rounded-full bg-electric px-4 py-1.5 text-xs font-semibold whitespace-nowrap text-white shadow-lg shadow-electric/40">
                    <Sparkles className="size-3.5" />
                    Most Popular
                  </span>
                )}

                <h3 className="text-lg font-semibold tracking-tight text-white">
                  {plan.name}
                </h3>
                <p className="mt-1 text-sm text-gray-500">{plan.tagline}</p>

                <p className="mt-6 flex items-baseline gap-1.5">
                  <span className="text-4xl font-bold tracking-tight text-white">
                    {plan.price}
                  </span>
                  <span className="text-sm text-gray-500">{plan.period}</span>
                </p>

                <ul className="mt-7 flex flex-col gap-3.5 border-t border-line pt-7">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-start gap-3 text-sm text-gray-300">
                      <span
                        className={cn(
                          "mt-0.5 flex size-4.5 shrink-0 items-center justify-center rounded-full",
                          plan.highlighted
                            ? "bg-electric/15 text-electric-bright"
                            : "bg-emerald/10 text-emerald"
                        )}
                      >
                        <Check className="size-3" />
                      </span>
                      {feature}
                    </li>
                  ))}
                </ul>

                <div className="mt-auto pt-8">
                  <Button
                    variant={plan.highlighted ? "primary" : "secondary"}
                    className="w-full"
                    size="lg"
                  >
                    {plan.cta}
                  </Button>
                </div>
              </article>
            </StaggerItem>
          ))}
        </Stagger>

        <p className="mt-10 text-center text-sm text-gray-500">
          All plans include your initial consultation and body-composition
          assessment — <span className="text-gray-300">free of charge</span>.
        </p>
      </div>
    </section>
  );
}
