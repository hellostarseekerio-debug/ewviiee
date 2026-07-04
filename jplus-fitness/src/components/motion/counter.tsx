"use client";

import { useEffect, useRef } from "react";
import { animate, useInView } from "framer-motion";

interface CounterProps {
  value: number;
  suffix?: string;
  decimals?: number;
  duration?: number;
  className?: string;
}

/** Animated number that counts up when scrolled into view. */
export function Counter({
  value,
  suffix = "",
  decimals = 0,
  duration = 2,
  className,
}: CounterProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });

  useEffect(() => {
    if (!inView || !ref.current) return;
    const node = ref.current;
    const controls = animate(0, value, {
      duration,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (latest) => {
        node.textContent = latest.toFixed(decimals) + suffix;
      },
    });
    return () => controls.stop();
  }, [inView, value, decimals, duration, suffix]);

  return (
    <span ref={ref} className={className}>
      {(0).toFixed(decimals) + suffix}
    </span>
  );
}
