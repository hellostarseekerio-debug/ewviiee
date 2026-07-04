"use client";

import Image from "next/image";
import { motion, useScroll, useTransform } from "framer-motion";
import { ArrowRight, Play, Star, TrendingUp } from "lucide-react";
import { useRef } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Counter } from "@/components/motion/counter";
import { heroStats } from "@/lib/data";

const ease = [0.22, 1, 0.36, 1] as const;

export function Hero() {
  const ref = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start start", "end start"],
  });
  const bgY = useTransform(scrollYProgress, [0, 1], ["0%", "18%"]);
  const fade = useTransform(scrollYProgress, [0, 0.7], [1, 0]);

  return (
    <section
      id="home"
      ref={ref}
      className="relative flex min-h-svh items-center justify-center overflow-hidden"
    >
      {/* Parallax background */}
      <motion.div style={{ y: bgY }} className="absolute inset-0 -z-10">
        <Image
          src="https://images.unsplash.com/photo-1571902943202-507ec2618e8f?q=80&w=2400&auto=format&fit=crop"
          alt="Premium private training studio in low light"
          fill
          priority
          className="object-cover"
          sizes="100vw"
        />
        <div className="absolute inset-0 bg-background/70" />
        <div className="absolute inset-0 bg-gradient-to-b from-background/60 via-background/40 to-background" />
      </motion.div>

      {/* Ambient glow */}
      <div className="pointer-events-none absolute -top-40 left-1/2 -z-10 h-[560px] w-[900px] -translate-x-1/2 rounded-full bg-electric/15 blur-[140px]" />

      <motion.div
        style={{ opacity: fade }}
        className="mx-auto w-full max-w-7xl px-6 pt-36 pb-24 text-center"
      >
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease, delay: 0.1 }}
        >
          <Badge className="mb-8">
            <Star className="size-3 fill-emerald text-emerald" />
            Rated 5.0 on Google · 27 five-star reviews
          </Badge>
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 32 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.9, ease, delay: 0.2 }}
          className="mx-auto max-w-5xl text-5xl font-bold tracking-tighter text-balance sm:text-6xl md:text-7xl lg:text-8xl"
        >
          <span className="text-gradient">Transform Your Body With </span>
          <span className="text-gradient-electric">Hong Kong&apos;s Elite</span>
          <span className="text-gradient"> Personal Trainers</span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.9, ease, delay: 0.35 }}
          className="mx-auto mt-7 max-w-2xl text-base leading-relaxed text-gray-400 md:text-lg"
        >
          Science-based, one-on-one coaching in the heart of Central. Personalized
          programs, precise body-composition tracking and world-class trainers —
          built entirely around you.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.9, ease, delay: 0.5 }}
          className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row"
        >
          <Button size="lg" className="w-full sm:w-auto">
            Book Your Free Consultation
            <ArrowRight className="size-4 transition-transform duration-300 group-hover:translate-x-1" />
          </Button>
          <Button variant="secondary" size="lg" className="w-full sm:w-auto">
            <Play className="size-4 fill-current" />
            Watch the Studio
          </Button>
        </motion.div>

        {/* Stats */}
        <motion.dl
          initial={{ opacity: 0, y: 32 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1, ease, delay: 0.7 }}
          className="glass mx-auto mt-20 grid max-w-4xl grid-cols-2 gap-y-8 rounded-3xl px-6 py-8 md:grid-cols-4 md:py-10"
        >
          {heroStats.map((stat) => (
            <div key={stat.label} className="flex flex-col items-center gap-1.5">
              <dd className="text-3xl font-bold tracking-tight text-white md:text-4xl">
                <Counter
                  value={stat.value}
                  suffix={stat.suffix}
                  decimals={stat.decimals ?? 0}
                />
              </dd>
              <dt className="text-xs font-medium tracking-wide text-gray-500 uppercase">
                {stat.label}
              </dt>
            </div>
          ))}
        </motion.dl>
      </motion.div>

      {/* Floating UI accents */}
      <motion.div
        initial={{ opacity: 0, x: -40 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 1, ease, delay: 1 }}
        className="absolute top-[24%] left-6 hidden lg:block xl:left-16"
      >
        <div className="glass animate-float rounded-2xl p-4 shadow-2xl shadow-black/40">
          <div className="flex items-center gap-3">
            <span className="flex size-10 items-center justify-center rounded-xl bg-emerald/15 text-emerald">
              <TrendingUp className="size-5" />
            </span>
            <div className="text-left">
              <p className="text-sm font-semibold text-white">−8.4% Body Fat</p>
              <p className="text-xs text-gray-500">Avg. client · 16 weeks</p>
            </div>
          </div>
        </div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, x: 40 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 1, ease, delay: 1.15 }}
        className="absolute top-[38%] right-6 hidden lg:block xl:right-16"
      >
        <div className="glass animate-float-slow rounded-2xl p-4 shadow-2xl shadow-black/40">
          <div className="flex items-center gap-3">
            <div className="flex -space-x-2">
              {[
                "photo-1544005313-94ddf0286df2",
                "photo-1507003211169-0a1dd7228f2d",
                "photo-1494790108377-be9c29b29330",
              ].map((id) => (
                <Image
                  key={id}
                  src={`https://images.unsplash.com/${id}?q=80&w=80&auto=format&fit=crop`}
                  alt=""
                  width={28}
                  height={28}
                  className="size-7 rounded-full border-2 border-card object-cover"
                />
              ))}
            </div>
            <div className="text-left">
              <div className="flex gap-0.5">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Star key={i} className="size-3 fill-emerald text-emerald" />
                ))}
              </div>
              <p className="text-xs text-gray-500">500+ clients transformed</p>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Scroll hint */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.6, duration: 1 }}
        className="absolute bottom-8 left-1/2 -translate-x-1/2"
      >
        <motion.div
          animate={{ y: [0, 8, 0] }}
          transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
          className="flex h-10 w-6 items-start justify-center rounded-full border border-line-strong p-1.5"
        >
          <span className="block h-2 w-1 rounded-full bg-gray-400" />
        </motion.div>
      </motion.div>
    </section>
  );
}
