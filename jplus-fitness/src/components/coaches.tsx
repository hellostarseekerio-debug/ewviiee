"use client";

import Image from "next/image";
import { Award, BadgeCheck, Quote } from "lucide-react";
import { SectionTitle } from "@/components/section-title";
import { Reveal, Stagger, StaggerItem } from "@/components/motion/reveal";
import { Badge } from "@/components/ui/badge";
import { coaches } from "@/lib/data";

export function Coaches() {
  const featured = coaches.find((c) => c.featured)!;
  const others = coaches.filter((c) => !c.featured);

  return (
    <section id="trainers" className="relative scroll-mt-24 border-y border-line bg-card/40 py-24 md:py-36">
      <div className="mx-auto max-w-7xl px-6">
        <SectionTitle
          eyebrow="Meet the Coaches"
          title="World-Class Coaching, One Client at a Time"
          subtitle="Certified, experienced and obsessed with detail — the team behind every transformation."
        />

        {/* Featured coach */}
        <Reveal>
          <article className="group grid overflow-hidden rounded-3xl border border-line bg-card lg:grid-cols-2">
            <div className="relative aspect-[4/3] overflow-hidden lg:aspect-auto lg:min-h-[520px]">
              <Image
                src={featured.image}
                alt={`${featured.name}, ${featured.role}`}
                fill
                className="object-cover transition-transform duration-700 group-hover:scale-105"
                sizes="(min-width: 1024px) 50vw, 100vw"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-card via-transparent lg:bg-gradient-to-r" />
              <Badge className="absolute top-5 left-5 border-electric/40 bg-electric/15 text-electric-bright">
                <Award className="size-3.5" />
                Featured Coach
              </Badge>
            </div>

            <div className="flex flex-col justify-center p-8 md:p-12">
              <h3 className="text-3xl font-bold tracking-tight text-white md:text-4xl">
                Coach {featured.name}
              </h3>
              <p className="mt-1.5 text-sm font-medium text-electric-bright">
                {featured.role} · {featured.experience}
              </p>

              <blockquote className="relative mt-7 border-l-2 border-electric/50 pl-5 text-base leading-relaxed text-gray-300 italic">
                <Quote className="absolute -top-1 -left-3 size-5 rounded-full bg-card text-electric" />
                {featured.philosophy}
              </blockquote>

              <div className="mt-8">
                <p className="text-xs font-semibold tracking-widest text-gray-500 uppercase">
                  Certifications
                </p>
                <ul className="mt-3 flex flex-wrap gap-2">
                  {featured.certifications.map((cert) => (
                    <li
                      key={cert}
                      className="flex items-center gap-1.5 rounded-full border border-line-strong bg-white/[0.03] px-3 py-1.5 text-xs text-gray-300"
                    >
                      <BadgeCheck className="size-3.5 text-emerald" />
                      {cert}
                    </li>
                  ))}
                </ul>
              </div>

              <div className="mt-6">
                <p className="text-xs font-semibold tracking-widest text-gray-500 uppercase">
                  Areas of Expertise
                </p>
                <ul className="mt-3 flex flex-wrap gap-2">
                  {featured.expertise.map((area) => (
                    <li
                      key={area}
                      className="rounded-full bg-electric/10 px-3 py-1.5 text-xs font-medium text-electric-bright"
                    >
                      {area}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </article>
        </Reveal>

        {/* Supporting coaches */}
        <Stagger className="mt-6 grid gap-6 md:grid-cols-2" stagger={0.12}>
          {others.map((coach) => (
            <StaggerItem key={coach.name}>
              <article className="group flex h-full flex-col overflow-hidden rounded-3xl border border-line bg-card transition-all duration-500 hover:border-line-strong hover:-translate-y-1.5 hover:shadow-2xl hover:shadow-black/40 sm:flex-row">
                <div className="relative aspect-[4/3] shrink-0 overflow-hidden sm:aspect-auto sm:w-2/5">
                  <Image
                    src={coach.image}
                    alt={`${coach.name}, ${coach.role}`}
                    fill
                    className="object-cover transition-transform duration-700 group-hover:scale-105"
                    sizes="(min-width: 640px) 20vw, 100vw"
                  />
                </div>
                <div className="flex flex-col p-6 md:p-7">
                  <h3 className="text-xl font-semibold tracking-tight text-white">
                    {coach.name}
                  </h3>
                  <p className="mt-0.5 text-sm text-electric-bright">{coach.role}</p>
                  <p className="mt-3 text-sm leading-relaxed text-gray-400">
                    {coach.philosophy}
                  </p>
                  <ul className="mt-auto flex flex-wrap gap-2 pt-5">
                    {coach.expertise.map((area) => (
                      <li
                        key={area}
                        className="rounded-full bg-white/[0.04] px-3 py-1 text-[11px] font-medium text-gray-300"
                      >
                        {area}
                      </li>
                    ))}
                  </ul>
                </div>
              </article>
            </StaggerItem>
          ))}
        </Stagger>
      </div>
    </section>
  );
}
