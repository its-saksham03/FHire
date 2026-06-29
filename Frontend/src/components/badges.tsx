import { cn, CONFIDENCE_COLORS, CAREER_DNA_COLORS } from "@/lib/utils";

export function ConfidenceBadge({ confidence }: { confidence: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 font-mono text-xs uppercase tracking-widest",
        CONFIDENCE_COLORS[confidence] ?? "bg-surface-container-high text-on-surface-variant"
      )}
    >
      {confidence}
    </span>
  );
}

export function CareerDNABadge({ dna }: { dna: string }) {
  const isDisqualifier = dna === "Consulting Only";
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 font-mono text-xs",
        CAREER_DNA_COLORS[dna] ?? "bg-surface-container-high text-on-surface-variant",
        isDisqualifier && "ring-1 ring-error/50"
      )}
      title={isDisqualifier ? "JD disqualifier signal" : undefined}
    >
      {dna}
      {isDisqualifier && (
        <span className="material-symbols-outlined ml-1 text-[14px] text-error">warning</span>
      )}
    </span>
  );
}

export function ScorePill({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const colorClass =
    score >= 0.75 ? "liquid-fill" : score >= 0.5 ? "liquid-fill-yellow" : "liquid-fill-risk";
  const text = `${(score * 100).toFixed(1)}%`;

  return (
    <div className="relative h-7 w-[72px] select-none overflow-hidden rounded-full bg-surface-container-highest">
      {/* Unfilled background text (visible on the dark background - light text) */}
      <div className="absolute inset-0 flex items-center justify-center font-mono text-xs font-medium text-on-surface-variant/90">
        {text}
      </div>
      
      {/* Progress fill */}
      <div
        className={cn("absolute inset-y-0 left-0 rounded-full overflow-hidden transition-all duration-300", colorClass)}
        style={{ width: `${pct}%` }}
      >
        {/* Filled overlay text (visible on the bright filled background - dark text for contrast) */}
        <div className="absolute inset-0 flex w-[72px] items-center justify-center font-mono text-xs font-medium text-black">
          {text}
        </div>
      </div>
    </div>
  );
}
