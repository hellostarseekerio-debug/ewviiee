"use client";

import Image from "next/image";
import { ClipboardCheck, LineChart, Salad, Target } from "lucide-react";
import { Reveal, Stagger, StaggerItem } from "@/components/motion/reveal";
import { Badge } from "@/components/ui/badge";

const features = [
  {
    icon: Target,
    title: "Personalized Coaching",
    description:
      "No templates. Every program is engineered around your body, goals and schedule.",
  },
  {
    icon: LineChart,
    title: "Body Composition Analysis",
    description:
      "Regular scans of body fat and lean mass keep every decision data-driven.",
  },
  {
    icon: Salad,
    title: "Nutrition Guidance",
    description:
      "Practical eating strategies built for real life in Hong Kong — no crash diets.",
  },
  {
    icon: ClipboardCheck,
    title: "Sustainable Progress",
    description:
      "Long-term planning and habit coaching so results last well beyond the program.",
  },
];

export function About() {
  return (
    <section id="about" className="relative mx-auto max-w-7xl scroll-mt-24 px-6 py-24 md:py-36">
      <div className="grid items-center gap-14 lg:grid-cols-2 lg:gap-20">
        {/* Image side */}
        <Reveal className="relative">
          <div className="relative aspect-[4/5] overflow-hidden rounded-3xl border border-line">
            <Image
              src="https://images.unsplash.com/photo-1574680096145-d05b474e2155?q=80&w=1600&auto=format&fit=crop"
              alt="Coach guiding a client through a training session"
              fill
              className="object-cover transition-transform duration-700 hover:scale-105"
              sizes="(min-width: 1024px) 50vw, 100vw"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-background/70 via-transparent" />
          </div>

          {/* Floating stat card */}
          <div className="glass absolute -right-4 -bottom-6 hidden rounded-2xl p-5 shadow-2xl shadow-black/50 sm:block md:-right-8">
            <p className="text-3xl font-bold text-white">
              98<span className="text-electric-bright">%</span>
            </p>
            <p className="mt-1 max-w-[160px] text-xs leading-relaxed text-gray-400">
              of members hit their first milestone within 8 weeks
            </p>
          </div>
        </Reveal>

        {/* Copy side */}
        <div>
          <Reveal>
            <Badge className="mb-5">
              <span className="size-1.5 rounded-full bg-emerald" />
              About J Plus Fitness
            </Badge>
            <h2 className="text-gradient text-4xl font-bold tracking-tight text-balance sm:text-5xl">
              Coaching Built on Science. Results Built to Last.
            </h2>
            <p className="mt-6 text-base leading-relaxed text-gray-400 md:text-lg">
              Tucked above Stanley Street in the heart of Central, J Plus Fitness
              is a private personal-training studio — not a crowded commercial
              gym. Every client trains one-on-one with an elite coach, following
              a program designed from a full assessment of their body
              composition, movement and lifestyle.
            </p>
          </Reveal>

          <Stagger className="mt-10 grid gap-4 sm:grid-cols-2" stagger={0.08}>
            {features.map((f) => (
              <StaggerItem key={f.title}>
                <div className="group h-full rounded-2xl border border-line bg-card p-5 transition-all duration-300 hover:border-line-strong hover:bg-card-hover hover:-translate-y-1">
                  <span className="mb-4 flex size-10 items-center justify-center rounded-xl bg-electric/10 text-electric-bright transition-colors duration-300 group-hover:bg-electric/20">
                    <f.icon className="size-5" />
                  </span>
                  <h3 className="text-sm font-semibold text-white">{f.title}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-gray-400">
                    {f.description}
                  </p>
                </div>
              </StaggerItem>
            ))}
          </Stagger>
        </div>
      </div>
    </section>
  );
}
