import { cn, scoreBgClass } from "@/lib/utils";

interface ScoreBarProps {
  label: string;
  score: number;
  explanation?: string;
  highlight?: boolean;
  accent?: "secondary" | "tertiary" | "risk";
}

export function ScoreBar({ label, score, explanation, highlight, accent }: ScoreBarProps) {
  const fillClass =
    accent === "tertiary" || accent === "risk"
      ? "liquid-fill-risk"
      : scoreBgClass(score / 100);

  return (
    <div
      className={cn(
        "rounded-xl border p-4 transition-all duration-300",
        highlight 
          ? "border-tertiary/40 bg-tertiary/5 shadow-[0_0_15px_rgba(125,211,252,0.15)]" 
          : "border-white/5 bg-surface-container-low/40 glass-panel hover:border-white/10"
      )}
    >
      <div className="mb-2 flex items-center justify-between">
        <span className="font-headline-lg text-sm font-medium text-white/90">{label}</span>
        <span className="font-label-sm text-sm text-tertiary">{score}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-surface-container-highest">
        <div className={cn("h-full rounded-full transition-all duration-500", fillClass)} style={{ width: `${score}%` }} />
      </div>
      {explanation && (
        <p className="mt-2 font-label-sm text-xs text-on-surface-variant leading-relaxed">{explanation}</p>
      )}
    </div>
  );
}

interface DimensionBarsProps {
  scores: { capability: number; trajectory: number; recruitability: number; authenticity: number };
  explanations?: {
    capability: string;
    trajectory: string;
    recruitability: string;
    authenticity: string;
  };
  winnerSide?: "a" | "b" | null;
  compareScores?: { capability: number; trajectory: number; recruitability: number; authenticity: number };
}

export function DimensionBars({ scores, explanations, winnerSide, compareScores }: DimensionBarsProps) {
  const dims = [
    { key: "capability" as const, label: "Capability" },
    { key: "trajectory" as const, label: "Trajectory" },
    { key: "recruitability" as const, label: "Recruitability" },
    { key: "authenticity" as const, label: "Authenticity" },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {dims.map(({ key, label }) => {
        const aScore = scores[key];
        const bScore = compareScores?.[key];
        let highlight = false;
        if (compareScores && winnerSide) {
          if (winnerSide === "a" && aScore > (bScore ?? 0)) highlight = true;
          if (winnerSide === "b" && aScore < (bScore ?? 0)) highlight = true;
        }
        const isRecruitRisk = key === "recruitability" && aScore < 50;
        return (
          <ScoreBar
            key={key}
            label={label}
            score={aScore}
            explanation={explanations?.[key]}
            highlight={highlight}
            accent={isRecruitRisk ? "risk" : undefined}
          />
        );
      })}
    </div>
  );
}
