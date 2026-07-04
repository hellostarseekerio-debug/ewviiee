"use client";

import { Reveal } from "@/components/motion/reveal";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface SectionTitleProps {
  eyebrow: string;
  title: React.ReactNode;
  subtitle?: string;
  align?: "left" | "center";
  className?: string;
}

export function SectionTitle({
  eyebrow,
  title,
  subtitle,
  align = "center",
  className,
}: SectionTitleProps) {
  return (
    <Reveal
      className={cn(
        "mb-14 max-w-3xl md:mb-20",
        align === "center" ? "mx-auto text-center" : "text-left",
        className
      )}
    >
      <Badge className="mb-5">
        <span className="size-1.5 rounded-full bg-electric" />
        {eyebrow}
      </Badge>
      <h2 className="text-gradient text-4xl font-bold tracking-tight text-balance sm:text-5xl md:text-6xl">
        {title}
      </h2>
      {subtitle && (
        <p className="mt-5 text-base leading-relaxed text-gray-400 md:text-lg">
          {subtitle}
        </p>
      )}
    </Reveal>
  );
}
