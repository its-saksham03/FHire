"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("animate-pulse rounded bg-surface-container-high/40 border border-white/5", className)}
      {...props}
    />
  );
}

export { Skeleton };
