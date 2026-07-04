"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Plus } from "lucide-react";
import { SectionTitle } from "@/components/section-title";
import { Stagger, StaggerItem } from "@/components/motion/reveal";
import { faqs } from "@/lib/data";
import { cn } from "@/lib/utils";

export function Faq() {
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  return (
    <section id="faq" className="mx-auto max-w-3xl scroll-mt-24 px-6 py-24 md:py-36">
      <SectionTitle
        eyebrow="FAQ"
        title="Questions, Answered"
        subtitle="Everything you need to know before your first session."
      />

      <Stagger className="flex flex-col gap-3" stagger={0.06}>
        {faqs.map((faq, i) => {
          const open = openIndex === i;
          return (
            <StaggerItem key={faq.question}>
              <div
                className={cn(
                  "overflow-hidden rounded-2xl border transition-colors duration-300",
                  open ? "border-line-strong bg-card-hover" : "border-line bg-card"
                )}
              >
                <button
                  type="button"
                  onClick={() => setOpenIndex(open ? null : i)}
                  aria-expanded={open}
                  className="flex w-full cursor-pointer items-center justify-between gap-4 px-6 py-5 text-left"
                >
                  <span className="text-sm font-semibold text-white md:text-base">
                    {faq.question}
                  </span>
                  <motion.span
                    animate={{ rotate: open ? 45 : 0 }}
                    transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
                    className={cn(
                      "flex size-8 shrink-0 items-center justify-center rounded-full border transition-colors duration-300",
                      open
                        ? "border-electric/40 bg-electric/15 text-electric-bright"
                        : "border-line-strong text-gray-400"
                    )}
                  >
                    <Plus className="size-4" />
                  </motion.span>
                </button>

                <AnimatePresence initial={false}>
                  {open && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
                    >
                      <p className="px-6 pb-6 text-sm leading-relaxed text-gray-400">
                        {faq.answer}
                      </p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </StaggerItem>
          );
        })}
      </Stagger>
    </section>
  );
}
