"use client";

import { motion } from "framer-motion";
import { SectionTitle } from "@/components/section-title";
import { processSteps } from "@/lib/data";
import { cn } from "@/lib/utils";

const ease = [0.22, 1, 0.36, 1] as const;

export function Process() {
  return (
    <section id="process" className="relative mx-auto max-w-5xl scroll-mt-24 px-6 py-24 md:py-36">
      <SectionTitle
        eyebrow="The Method"
        title="Your Journey, Engineered"
        subtitle="A proven six-step system that turns first consultations into lasting transformations."
      />

      <ol className="relative">
        {/* Spine */}
        <motion.div
          initial={{ scaleY: 0 }}
          whileInView={{ scaleY: 1 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 1.6, ease }}
          className="absolute top-2 bottom-2 left-[19px] w-px origin-top bg-gradient-to-b from-electric via-emerald to-transparent md:left-1/2"
        />

        {processSteps.map((step, i) => {
          const left = i % 2 === 0;
          return (
            <motion.li
              key={step.step}
              initial={{ opacity: 0, y: 32 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ duration: 0.7, ease, delay: 0.1 }}
              className={cn(
                "relative mb-10 flex items-start gap-6 pl-14 last:mb-0 md:w-1/2 md:gap-0 md:pl-0",
                left
                  ? "md:mr-auto md:pr-14 md:text-right"
                  : "md:ml-auto md:pl-14"
              )}
            >
              {/* Node */}
              <span
                aria-hidden
                className={cn(
                  "absolute top-1 left-2.5 flex size-4 items-center justify-center md:left-auto",
                  left
                    ? "md:-right-2 md:translate-x-px"
                    : "md:-left-2 md:-translate-x-px"
                )}
              >
                <span className="absolute size-4 animate-ping rounded-full bg-electric/30" />
                <span className="relative size-2.5 rounded-full bg-electric shadow-[0_0_12px_rgba(47,125,255,0.9)]" />
              </span>

              <div className="group w-full rounded-2xl border border-line bg-card p-6 transition-all duration-300 hover:border-line-strong hover:bg-card-hover hover:-translate-y-1">
                <span className="font-mono text-xs font-semibold tracking-widest text-electric-bright">
                  STEP {step.step}
                </span>
                <h3 className="mt-2 text-xl font-semibold tracking-tight text-white">
                  {step.title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-gray-400">
                  {step.description}
                </p>
              </div>
            </motion.li>
          );
        })}
      </ol>
    </section>
  );
}
