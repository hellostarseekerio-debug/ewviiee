import { cn } from "@/lib/utils";

export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn("flex items-center gap-2.5", className)}>
      <span className="flex size-9 items-center justify-center rounded-xl bg-electric font-bold text-white shadow-[0_0_24px_-6px_rgba(47,125,255,0.8)]">
        J+
      </span>
      <span className="text-[15px] font-semibold tracking-tight text-white">
        J Plus Fitness
        <span className="block text-[10px] font-medium tracking-[0.22em] text-gray-500 uppercase">
          Central · Hong Kong
        </span>
      </span>
    </span>
  );
}
