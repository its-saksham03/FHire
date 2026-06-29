"use client";

import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded font-label-sm text-xs uppercase tracking-wider transition-all focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-tertiary disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "frozen-glow text-white hover:bg-white/5 shadow-[0_0_15px_rgba(125,211,252,0.15)] hover:scale-[1.02] active:scale-95 duration-200",
        outline: "border border-white/5 bg-white/[0.02] text-on-surface-variant hover:text-white hover:border-white/20 hover:bg-white/[0.05] active:scale-95 duration-200",
        ghost: "hover:bg-surface-container-high/40 text-on-surface-variant hover:text-white active:scale-95 duration-200",
        risk: "bg-error/10 text-error border border-error/25 hover:bg-error/20 active:scale-95 duration-200",
        tertiary: "frozen-glow text-white hover:bg-white/5 hover:border-tertiary shadow-[0_0_20px_rgba(125,211,252,0.15)] duration-200",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 px-3 text-[11px]",
        lg: "h-11 px-6 text-sm",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />;
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
