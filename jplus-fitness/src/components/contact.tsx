"use client";

import { Clock, Mail, MapPin, Phone, Send } from "lucide-react";
import { SectionTitle } from "@/components/section-title";
import { Reveal } from "@/components/motion/reveal";
import { Button } from "@/components/ui/button";
import { contactInfo } from "@/lib/data";

const inputClasses =
  "w-full rounded-xl border border-line bg-white/[0.03] px-4 py-3 text-sm text-white placeholder:text-gray-600 transition-colors duration-300 focus:border-electric/60 focus:bg-white/[0.05] focus:outline-none";

export function Contact() {
  return (
    <section id="contact" className="scroll-mt-24 border-t border-line bg-card/40 py-24 md:py-36">
      <div className="mx-auto max-w-7xl px-6">
        <SectionTitle
          eyebrow="Get in Touch"
          title="Visit Us in Central"
          subtitle="Two minutes from Central MTR. Drop by, call, or send us a message — we'd love to meet you."
        />

        <div className="grid gap-6 lg:grid-cols-5">
          {/* Info column */}
          <Reveal className="flex flex-col gap-6 lg:col-span-2">
            <div className="rounded-3xl border border-line bg-card p-8">
              <h3 className="text-lg font-semibold text-white">
                {contactInfo.company}
              </h3>

              <ul className="mt-7 flex flex-col gap-6">
                <li className="flex gap-4">
                  <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-electric/10 text-electric-bright">
                    <MapPin className="size-5" />
                  </span>
                  <address className="text-sm leading-relaxed text-gray-400 not-italic">
                    {contactInfo.addressLines.map((line) => (
                      <span key={line} className="block">
                        {line}
                      </span>
                    ))}
                  </address>
                </li>
                <li className="flex items-center gap-4">
                  <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-emerald/10 text-emerald">
                    <Phone className="size-5" />
                  </span>
                  <span className="text-sm text-gray-400">{contactInfo.phone}</span>
                </li>
                <li className="flex items-center gap-4">
                  <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-electric/10 text-electric-bright">
                    <Mail className="size-5" />
                  </span>
                  <span className="text-sm text-gray-400">{contactInfo.email}</span>
                </li>
                <li className="flex gap-4">
                  <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-emerald/10 text-emerald">
                    <Clock className="size-5" />
                  </span>
                  <dl className="flex flex-col gap-1.5 text-sm">
                    {contactInfo.hours.map((h) => (
                      <div key={h.days} className="flex flex-wrap gap-x-3">
                        <dt className="text-gray-400">{h.days}</dt>
                        <dd className="text-gray-300">{h.time}</dd>
                      </div>
                    ))}
                  </dl>
                </li>
              </ul>
            </div>

            {/* Map placeholder */}
            <div className="relative flex-1 min-h-56 overflow-hidden rounded-3xl border border-line bg-card">
              <div
                aria-hidden
                className="absolute inset-0 opacity-40"
                style={{
                  backgroundImage:
                    "linear-gradient(rgba(255,255,255,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.06) 1px, transparent 1px)",
                  backgroundSize: "36px 36px",
                }}
              />
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
                <span className="relative flex size-12 items-center justify-center">
                  <span className="absolute size-12 animate-ping rounded-full bg-electric/25" />
                  <span className="relative flex size-9 items-center justify-center rounded-full bg-electric text-white shadow-lg shadow-electric/50">
                    <MapPin className="size-4.5" />
                  </span>
                </span>
                <p className="text-sm font-medium text-white">
                  20 Stanley Street, Central
                </p>
                <p className="text-xs text-gray-500">Interactive map placeholder</p>
              </div>
            </div>
          </Reveal>

          {/* Form column */}
          <Reveal delay={0.15} className="lg:col-span-3">
            <form
              className="flex h-full flex-col rounded-3xl border border-line bg-card p-8 md:p-10"
              onSubmit={(e) => e.preventDefault()}
            >
              <h3 className="text-lg font-semibold text-white">
                Book Your Free Consultation
              </h3>
              <p className="mt-1.5 text-sm text-gray-500">
                Tell us about your goals — a coach will reply within one
                business day.
              </p>

              <div className="mt-8 grid gap-5 sm:grid-cols-2">
                <div className="flex flex-col gap-2">
                  <label htmlFor="name" className="text-xs font-medium tracking-wide text-gray-400 uppercase">
                    Name
                  </label>
                  <input id="name" placeholder="Your name" className={inputClasses} />
                </div>
                <div className="flex flex-col gap-2">
                  <label htmlFor="phone" className="text-xs font-medium tracking-wide text-gray-400 uppercase">
                    Phone
                  </label>
                  <input id="phone" placeholder="+852 ..." className={inputClasses} />
                </div>
                <div className="flex flex-col gap-2 sm:col-span-2">
                  <label htmlFor="email" className="text-xs font-medium tracking-wide text-gray-400 uppercase">
                    Email
                  </label>
                  <input
                    id="email"
                    type="email"
                    placeholder="you@example.com"
                    className={inputClasses}
                  />
                </div>
                <div className="flex flex-col gap-2 sm:col-span-2">
                  <label htmlFor="goal" className="text-xs font-medium tracking-wide text-gray-400 uppercase">
                    Your Goal
                  </label>
                  <textarea
                    id="goal"
                    rows={5}
                    placeholder="e.g. Lose body fat, build strength, prepare for an event..."
                    className={`${inputClasses} resize-none`}
                  />
                </div>
              </div>

              <div className="mt-auto pt-8">
                <Button size="lg" className="w-full sm:w-auto">
                  Send Message
                  <Send className="size-4 transition-transform duration-300 group-hover:translate-x-1 group-hover:-translate-y-0.5" />
                </Button>
                <p className="mt-4 text-xs text-gray-600">
                  Mockup only — this form does not submit data.
                </p>
              </div>
            </form>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
