"use client";

import { useEffect, useRef } from "react";

export function useFadeInUp() {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("visible");
          }
        });
      },
      { threshold: 0.1 }
    );

    el.querySelectorAll(".fade-in-up").forEach((child, i) => {
      (child as HTMLElement).style.transitionDelay = `${i * 200}ms`;
      observer.observe(child);
    });

    return () => observer.disconnect();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return ref;
}

export function LoadingSpinner({ label = "Loading..." }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-5 py-24 animate-pulse">
      <div className="w-48 h-[2px] bg-white/5 rounded-full premium-loading-bar" />
      <p className="font-label-sm text-[10px] uppercase tracking-[0.2em] text-tertiary/80 font-medium">{label}</p>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 rounded-xl border border-error/25 bg-error-container/20 p-8 text-center glass-panel">
      <span className="material-symbols-outlined text-4xl text-error">error</span>
      <p className="font-headline-lg text-headline-md text-white">{message}</p>
      <p className="font-label-sm text-xs text-on-surface-variant">
        The scoring engine may be temporarily unavailable. Your data is safe.
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="frozen-glow rounded px-4 py-2 font-label-sm text-xs uppercase tracking-wider text-white"
        >
          Retry
        </button>
      )}
    </div>
  );
}

export function TrajectorySparkline({ direction }: { direction: "up" | "flat" | "down" | "mixed" }) {
  const paths = {
    up: "M0,20 Q10,18 20,12 T40,4",
    flat: "M0,12 L40,12",
    down: "M0,4 Q10,8 20,14 T40,20",
    mixed: "M0,12 Q10,4 20,16 T40,8",
  };
  return (
    <svg width="40" height="24" viewBox="0 0 40 24" className="inline-block">
      <path
        d={paths[direction]}
        fill="none"
        stroke="#7dd3fc"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function SkeletonLoader({ label = "Evaluating Candidates..." }: { label?: string }) {
  return (
    <div className="space-y-4 py-4 w-full">
      {/* Status Header */}
      <div className="flex items-center gap-3 bg-surface-container-low/20 rounded border border-white/5 p-4 glass-panel animate-pulse">
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-tertiary border-t-transparent" />
        <p className="font-label-sm text-xs uppercase tracking-widest text-tertiary">{label}</p>
      </div>
      
      {/* 3 pulsing card rows simulating candidate list items */}
      {[1, 2, 3].map((i) => (
        <div key={i} className="rounded-xl border border-white/5 bg-surface-container-low/40 glass-panel p-5 space-y-4 animate-pulse">
          <div className="flex items-start justify-between">
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <div className="h-6 w-8 rounded bg-white/10" />
                <div className="h-4 w-20 rounded bg-white/5" />
              </div>
              <div className="flex gap-1.5">
                <div className="h-4 w-24 rounded bg-white/10" />
                <div className="h-4 w-16 rounded bg-white/10" />
              </div>
            </div>
            <div className="h-8 w-12 rounded-full bg-white/10" />
          </div>
          
          <div className="grid grid-cols-2 gap-4 rounded border border-white/5 bg-surface-container-low/30 p-3">
            <div className="space-y-1">
              <div className="h-3 w-16 rounded bg-white/5" />
              <div className="h-4 w-12 rounded bg-white/10" />
            </div>
            <div className="space-y-1">
              <div className="h-3 w-20 rounded bg-white/5" />
              <div className="h-4 w-12 rounded bg-white/10" />
            </div>
          </div>
          
          <div className="h-10 w-full rounded bg-white/5" />
        </div>
      ))}
    </div>
  );
}
