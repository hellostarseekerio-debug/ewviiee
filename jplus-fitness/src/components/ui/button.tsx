import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "group inline-flex cursor-pointer items-center justify-center gap-2 rounded-full font-medium tracking-tight transition-all duration-300 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-electric disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        primary:
          "bg-electric text-white shadow-[0_0_30px_-8px_rgba(47,125,255,0.7)] hover:bg-electric-bright hover:shadow-[0_0_45px_-6px_rgba(47,125,255,0.85)] hover:-translate-y-0.5 active:translate-y-0",
        secondary:
          "glass-bright text-white hover:bg-white/10 hover:-translate-y-0.5 active:translate-y-0",
        ghost: "text-gray-400 hover:text-white hover:bg-white/5",
        white:
          "bg-white text-black hover:bg-gray-200 hover:-translate-y-0.5 active:translate-y-0",
      },
      size: {
        sm: "h-9 px-4 text-sm",
        md: "h-11 px-6 text-sm",
        lg: "h-13 px-8 text-base",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  )
);
Button.displayName = "Button";

export { Button, buttonVariants };
