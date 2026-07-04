"use client";

import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { Reveal } from "@/components/motion/reveal";
import { Button } from "@/components/ui/button";

export function CtaBanner() {
  return (
    <section aria-label="Call to action" className="px-6 py-24 md:py-32">
      <Reveal className="mx-auto max-w-7xl">
        <div className="relative overflow-hidden rounded-[2.5rem] border border-line bg-card px-8 py-20 text-center md:px-16 md:py-28">
          {/* Animated aurora background */}
          <motion.div
            aria-hidden
            animate={{ x: ["-15%", "15%", "-15%"], y: ["-8%", "8%", "-8%"] }}
            transition={{ duration: 18, repeat: Infinity, ease: "easeInOut" }}
            className="pointer-events-none absolute -top-48 left-1/4 size-[520px] rounded-full bg-electric/20 blur-[140px]"
          />
          <motion.div
            aria-hidden
            animate={{ x: ["12%", "-12%", "12%"], y: ["6%", "-6%", "6%"] }}
            transition={{ duration: 22, repeat: Infinity, ease: "easeInOut" }}
            className="pointer-events-none absolute -bottom-48 right-1/4 size-[520px] rounded-full bg-emerald/15 blur-[140px]"
          />
          <div className="pointer-events-none absolute inset-0 grid-fade" />

          <div className="relative">
            <p className="text-xs font-semibold tracking-[0.3em] text-electric-bright uppercase">
              Limited coaching slots available
            </p>
            <h2 className="text-gradient mx-auto mt-5 max-w-3xl text-4xl font-bold tracking-tight text-balance sm:text-5xl md:text-6xl">
              Start Your Fitness Transformation Today
            </h2>
            <p className="mx-auto mt-6 max-w-xl text-base leading-relaxed text-gray-400 md:text-lg">
              Your free consultation and body-composition assessment are one
              click away. The best time to start was yesterday — the second
              best is now.
            </p>
            <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Button size="lg">
                Book Your Free Consultation
                <ArrowRight className="size-4 transition-transform duration-300 group-hover:translate-x-1" />
              </Button>
              <Button variant="secondary" size="lg">
                View Membership Plans
              </Button>
            </div>
          </div>
        </div>
      </Reveal>
    </section>
  );
}
