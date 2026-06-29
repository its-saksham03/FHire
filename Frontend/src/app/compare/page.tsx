"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { ScorePill } from "@/components/badges";
import { SignalField } from "@/components/signal-field";
import { ScoreBar } from "@/components/score-bar";
import { ErrorState, LoadingSpinner } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, compareCandidates } from "@/lib/api";
import type { CompareResult, DimensionComparison } from "@/lib/types";
import { cn, formatScore } from "@/lib/utils";

function sanitizeCandidateId(id: string | null | undefined): string | null {
  if (!id) return null;
  const cleaned = id.trim();
  if (/^CAND_[0-9]+$/.test(cleaned)) {
    return cleaned;
  }
  return null;
}

function CompareContent() {
  const searchParams = useSearchParams();
  const idA = searchParams.get("a") ?? "";
  const idB = searchParams.get("b") ?? "";
  const [result, setResult] = useState<CompareResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const cleanIdA = sanitizeCandidateId(idA);
    const cleanIdB = sanitizeCandidateId(idB);
    if (!cleanIdA || !cleanIdB) {
      setError("Invalid or missing candidate IDs. Format must be CAND_xxxxxxx.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setResult(await compareCandidates(cleanIdA, cleanIdB));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Comparison failed");
    } finally {
      setLoading(false);
    }
  }, [idA, idB]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <div className="mx-auto max-w-container px-margin-mobile py-8 md:px-margin-desktop pt-24">
        <LoadingSpinner label="Comparing candidates..." />
      </div>
    );
  }
  if (error || !result) {
    return (
      <div className="mx-auto max-w-container px-margin-mobile py-8 md:px-margin-desktop pt-24">
        <ErrorState message={error ?? "Comparison unavailable"} onRetry={load} />
        <div className="mt-4 text-center">
          <Button asChild variant="outline">
            <Link href="/rankings">Back to Rankings</Link>
          </Button>
        </div>
      </div>
    );
  }

  const { candidate_a: a, candidate_b: b } = result;

  // Check winner by comparing final scores
  const aIsWinner = result.final_score_a >= result.final_score_b;

  return (
    <div className="relative">
      <SignalField opacity={0.12} />

      <div className="relative z-10 mx-auto max-w-container px-margin-mobile py-8 md:px-margin-desktop pt-24 space-y-6">
        <Button asChild variant="ghost" className="mb-6">
          <Link href="/rankings">← Back to Candidates</Link>
        </Button>

        <header className="mb-10 text-center space-y-1">
          <p className="font-label-sm text-xs uppercase tracking-wider text-tertiary">
            Head-to-Head
          </p>
          <h1 className="font-headline-lg text-headline-xl text-white">
            {a.current_title}{" "}
            <span className="text-on-surface-variant not-italic font-light">vs</span>{" "}
            {b.current_title}
          </h1>
        </header>

        {/* Top scores */}
        <div className="mb-10 grid gap-6 md:grid-cols-2">
          <CandidateCard
            meta={a}
            finalScore={result.final_score_a}
            accent="secondary"
            isWinner={aIsWinner}
            side="A"
          />
          <CandidateCard
            meta={b}
            finalScore={result.final_score_b}
            accent="tertiary"
            isWinner={!aIsWinner}
            side="B"
          />
        </div>

        {/* Dimension comparison */}
        <section className="mb-10 space-y-4">
          <h2 className="mb-6 font-headline-lg text-headline-md text-white text-center">Dimension Comparison</h2>
          <div className="space-y-3">
            {result.dimension_comparisons.map((dim) => (
              <DimensionRow key={dim.dimension} dim={dim} />
            ))}
          </div>
        </section>

        {/* Reasoning */}
        <div className="mb-8 grid gap-6 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="font-label-sm text-[10px] uppercase tracking-wider text-tertiary">
                Candidate A Reasoning
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm leading-relaxed text-on-surface-variant">{result.reasoning_a}</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="font-label-sm text-[10px] uppercase tracking-wider text-tertiary">
                Candidate B Reasoning
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm leading-relaxed text-on-surface-variant">{result.reasoning_b}</p>
            </CardContent>
          </Card>
        </div>

        {/* Verdict */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <span className="material-symbols-outlined text-tertiary">insights</span>
              AI Synthetic Verdict
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="font-body-md text-sm text-white/95 leading-relaxed">{result.verdict}</p>
            {result.dimensions_a_wins.length > 0 && (
              <p className="font-label-sm text-xs text-on-surface-variant">
                Candidate A wins: {result.dimensions_a_wins.join(", ")}
              </p>
            )}
            {result.dimensions_b_wins.length > 0 && (
              <p className="font-label-sm text-xs text-on-surface-variant">
                Candidate B wins: {result.dimensions_b_wins.join(", ")}
              </p>
            )}
            <p className="font-data-mono text-xs text-secondary border-t border-white/5 pt-3">
              Score delta:{" "}
              <span className={aIsWinner ? "text-tertiary font-medium" : "text-secondary font-medium"}>
                {result.final_score_diff > 0 ? "+" : ""}
                {(result.final_score_diff * 100).toFixed(1)}%
              </span>
            </p>
          </CardContent>
        </Card>

        <div className="mt-8 flex flex-wrap justify-center gap-4">
          <Button asChild variant="outline">
            <Link href={`/candidate/${encodeURIComponent(a.candidate_id)}`}>View {a.candidate_id}</Link>
          </Button>
          <Button asChild variant="outline">
            <Link href={`/candidate/${encodeURIComponent(b.candidate_id)}`}>View {b.candidate_id}</Link>
          </Button>
        </div>
      </div>
    </div>
  );
}

function DimensionRow({ dim }: { dim: DimensionComparison }) {
  const aWins = dim.winner === "A";
  const bWins = dim.winner === "B";
  return (
    <div className="rounded border border-white/5 bg-surface-container-low/40 glass-panel p-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="font-headline-lg text-sm font-medium text-white/90">{dim.dimension}</span>
        <span
          className={cn(
            "font-label-sm text-[10px] uppercase tracking-wider",
            dim.winner === "tie" ? "text-on-surface-variant" : "text-tertiary"
          )}
        >
          {dim.advantage}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <ScoreBar
          label={`A — ${dim.score_a.toFixed(1)}`}
          score={dim.score_a}
          highlight={aWins}
        />
        <ScoreBar
          label={`B — ${dim.score_b.toFixed(1)}`}
          score={dim.score_b}
          highlight={bWins}
          accent="tertiary"
        />
      </div>
    </div>
  );
}

function CandidateCard({
  meta,
  finalScore,
  accent,
  isWinner,
  side,
}: {
  meta: CompareResult["candidate_a"];
  finalScore: number;
  accent: "secondary" | "tertiary";
  isWinner: boolean;
  side: "A" | "B";
}) {
  const borderColor =
    accent === "secondary" ? "border-secondary/20" : "border-tertiary/20";
  const textColor =
    accent === "secondary" ? "text-secondary" : "text-tertiary";

  return (
    <div
      className={cn(
        "rounded border bg-surface-container-low/40 glass-panel p-6 transition-all duration-300",
        borderColor,
        isWinner && "shadow-[0_0_20px_rgba(125,211,252,0.15)] frozen-glow"
      )}
    >
      <p className={cn("font-label-sm text-[10px] uppercase tracking-wider", textColor)}>
        Candidate {side} · {meta.candidate_id}
      </p>
      <h3 className="mt-2 font-headline-lg text-lg text-white/95">{meta.current_title}</h3>
      <p className="text-xs text-on-surface-variant mt-0.5">{meta.location}</p>
      <p className="text-xs text-on-surface-variant font-label-sm mt-1">
        {meta.career_dna} · {meta.years_of_experience.toFixed(1)} yrs
      </p>
      <div className="mt-4 flex items-center gap-3">
        <ScorePill score={finalScore} />
        {meta.open_to_work && (
          <span className="font-label-sm text-xs text-tertiary">Open to Work</span>
        )}
        {meta.notice_period != null && (
          <span className="font-data-mono text-xs text-on-surface-variant">
            {meta.notice_period}d notice
          </span>
        )}
      </div>
      {isWinner && (
        <p className={cn("mt-3 font-label-sm text-[10px] uppercase tracking-wider", textColor)}>
          Higher composite score
        </p>
      )}
    </div>
  );
}

export default function ComparePage() {
  return (
    <Suspense fallback={
      <div className="mx-auto max-w-container px-margin-mobile py-8 md:px-margin-desktop pt-24">
        <LoadingSpinner label="Loading comparison..." />
      </div>
    }>
      <CompareContent />
    </Suspense>
  );
}
