"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { CareerDNABadge, ConfidenceBadge } from "@/components/badges";
import { SignalField } from "@/components/signal-field";
import { DimensionBars } from "@/components/score-bar";
import { ErrorState, LoadingSpinner } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, getCandidateDetail } from "@/lib/api";
import type { CandidateDetail } from "@/lib/types";
import { cn, formatScore, trustScoreColor } from "@/lib/utils";

function sanitizeCandidateId(id: string | null | undefined): string | null {
  if (!id) return null;
  const cleaned = id.trim();
  if (/^CAND_[0-9]+$/.test(cleaned)) {
    return cleaned;
  }
  return null;
}

export default function CandidateDetailPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const fromSource = searchParams.get("from") ?? undefined;
  const context = searchParams.get("context") ?? undefined;
  
  const id = params.id as string;
  const [candidate, setCandidate] = useState<CandidateDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const cleanId = sanitizeCandidateId(id);
    if (!cleanId) {
      setError("Invalid candidate ID format. Format must be CAND_xxxxxxx.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setCandidate(await getCandidateDetail(cleanId, fromSource, context));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load candidate");
    } finally {
      setLoading(false);
    }
  }, [id, fromSource, context]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <div className="mx-auto max-w-container px-margin-mobile py-8 md:px-margin-desktop pt-24">
        <Skeleton className="mb-4 h-8 w-48" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  if (error || !candidate) {
    return (
      <div className="mx-auto max-w-container px-margin-mobile py-8 md:px-margin-desktop pt-24">
        <ErrorState message={error ?? "Candidate not found"} onRetry={load} />
        <div className="mt-4 text-center">
          <Button asChild variant="outline">
            <Link href="/rankings">Back to Rankings</Link>
          </Button>
        </div>
      </div>
    );
  }

  const { profile, signals } = candidate;

  // Build dimension scores in the format DimensionBars expects
  const scores = {
    capability: candidate.capability,
    trajectory: candidate.trajectory?.score ?? 0,
    recruitability: candidate.recruitability?.score ?? 0,
    authenticity: candidate.authenticity?.score ?? 0,
  };

  // Build score explanations from engine data
  const explanations = {
    capability: `Raw capability score: ${candidate.capability.toFixed(1)}/100`,
    trajectory: `Trajectory score: ${(candidate.trajectory?.score ?? 0).toFixed(1)}/100 — DNA: ${candidate.career_dna}`,
    recruitability: `Recruitability: ${(candidate.recruitability?.score ?? 0).toFixed(1)}/100 (multiplier: ${(candidate.recruitability?.multiplier ?? 1).toFixed(2)}×)`,
    authenticity: `Authenticity: ${(candidate.authenticity?.score ?? 0).toFixed(1)}/100${(candidate.authenticity?.flags?.length ?? 0) > 0 ? " — flags present" : ""}`,
  };

  return (
    <div className="relative min-h-screen">
      <SignalField opacity={0.1} className="fixed inset-0" />

      <div className="relative z-10 mx-auto max-w-container px-margin-mobile py-8 md:px-margin-desktop pt-24">
        <Button asChild variant="ghost" className="mb-6">
          <Link href="/rankings">
            <span className="material-symbols-outlined mr-1 text-base">arrow_back</span>
            Back to Candidates
          </Link>
        </Button>

        {/* ── Header ── */}
        <div className="mb-8 flex flex-wrap items-start justify-between gap-6">
          <div className="space-y-1">
            <p className="font-label-sm text-xs uppercase tracking-wider text-tertiary">
              {candidate.candidate_id}
            </p>
            <h1 className="font-headline-lg text-headline-lg text-white">{profile?.current_title ?? "—"}</h1>
            <p className="text-body-md text-on-surface-variant font-body-md">
              {profile?.current_company ?? "—"} · {profile?.location ?? "—"}
            </p>
            <div className="mt-3 flex flex-wrap gap-2 pt-1">
              <CareerDNABadge dna={candidate.career_dna} />
              <ConfidenceBadge confidence={candidate.confidence.label} />
              {candidate.rank != null && (
                <span className="rounded border border-white/5 bg-surface-container-low/40 px-3 py-0.5 font-label-sm text-xs text-white/80">
                  Rank #{candidate.rank}
                </span>
              )}
            </div>
          </div>
          <div className="rounded border border-tertiary/30 bg-tertiary/5 px-8 py-6 text-center shadow-[0_0_20px_rgba(125,211,252,0.15)] frozen-glow">
            <p className="font-label-sm text-[10px] uppercase tracking-wider text-secondary">
              Final Score
            </p>
            <p className="font-headline-xl text-5xl font-bold text-tertiary mt-1">
              {formatScore(candidate.final_score)}
            </p>
          </div>
        </div>

        {/* ── Recruiter Match Workspace Context ── */}
        {candidate.requirement_match && (
          <section className="mb-10 rounded border border-tertiary/20 bg-tertiary/5 glass-panel p-6 space-y-4 shadow-[0_0_20px_rgba(125,211,252,0.08)]">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <h2 className="font-headline-lg text-headline-md text-white flex items-center gap-2">
                  <span className="material-symbols-outlined text-tertiary">workspace_premium</span>
                  Recruiter Match Context
                </h2>
                <p className="font-label-sm text-xs text-on-surface-variant uppercase tracking-widest mt-1">
                  Evaluated against job intake requirements
                </p>
              </div>
              <div className="text-right">
                <span className="font-label-sm text-[10px] uppercase tracking-wider text-secondary">
                  Match Score
                </span>
                <p className="font-data-mono text-3xl font-bold text-tertiary">
                  {candidate.requirement_match.score.toFixed(0)}%
                </p>
              </div>
            </div>

            <div className="grid gap-6 md:grid-cols-2 pt-2 border-t border-white/5">
              {/* Matched & Missing Skills */}
              <div className="space-y-3">
                <h3 className="font-headline-lg text-sm font-semibold text-white/90">Skills Assessment</h3>
                
                <div className="space-y-2">
                  <span className="font-data-mono text-[10px] text-emerald-400 uppercase tracking-wider block">
                    Matched Skills
                  </span>
                  {candidate.requirement_match.matched_skills.length === 0 ? (
                    <p className="text-xs text-on-surface-variant italic">None</p>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {candidate.requirement_match.matched_skills.map((skill) => (
                        <span key={skill} className="inline-flex items-center gap-1 rounded bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-400 border border-emerald-500/10">
                          <span className="material-symbols-outlined text-[12px] font-bold">check</span>
                          {skill}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                <div className="space-y-2 pt-2">
                  <span className="font-data-mono text-[10px] text-error/80 uppercase tracking-wider block">
                    Missing Skills
                  </span>
                  {candidate.requirement_match.missing_skills.length === 0 ? (
                    <p className="text-xs text-on-surface-variant italic">None</p>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {candidate.requirement_match.missing_skills.map((skill) => (
                        <span key={skill} className="inline-flex items-center gap-1 rounded bg-error-container/10 px-2.5 py-1 text-xs font-medium text-error border border-error-container/10">
                          <span className="material-symbols-outlined text-[12px] font-bold">close</span>
                          {skill}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Location & Experience Checks */}
              <div className="space-y-3">
                <h3 className="font-headline-lg text-sm font-semibold text-white/90">Target Fit Checks</h3>
                
                <div className="space-y-2">
                  <div className="flex items-center justify-between rounded bg-white/5 p-2 text-xs">
                    <span className="text-on-surface-variant font-body-md">Location criteria:</span>
                    <span className={cn("font-medium flex items-center gap-1", candidate.requirement_match.location_matched ? "text-emerald-400" : "text-on-surface-variant opacity-60")}>
                      <span className="material-symbols-outlined text-[14px]">{candidate.requirement_match.location_matched ? "check_circle" : "cancel"}</span>
                      {candidate.requirement_match.location_matched ? "Matched" : "Not Matched"}
                    </span>
                  </div>

                  <div className="flex items-center justify-between rounded bg-white/5 p-2 text-xs">
                    <span className="text-on-surface-variant font-body-md">Experience criteria:</span>
                    <span className={cn("font-medium flex items-center gap-1", candidate.requirement_match.experience_matched ? "text-emerald-400" : "text-on-surface-variant opacity-60")}>
                      <span className="material-symbols-outlined text-[14px]">{candidate.requirement_match.experience_matched ? "check_circle" : "cancel"}</span>
                      {candidate.requirement_match.experience_matched ? "Matched" : "Not Matched"}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </section>
        )}

        {/* ── Dimension scores ── */}
        <section className="mb-10">
          <h2 className="mb-4 font-headline-lg text-headline-md text-white">Dimension Scores</h2>
          <DimensionBars scores={scores} explanations={explanations} />
        </section>

        {/* ── Recruitability breakdown ── */}
        {candidate.recruitability?.breakdown && (
          <section className="mb-10">
            <h2 className="mb-4 font-headline-lg text-headline-md text-white">Recruitability Breakdown</h2>
            <div className="grid gap-4 sm:grid-cols-3">
              {(
                [
                  { key: "availability", label: "Availability" },
                  { key: "responsiveness", label: "Responsiveness" },
                  { key: "logistics", label: "Logistics" },
                ] as const
              ).map(({ key, label }) => {
                const val = candidate.recruitability.breakdown[key];
                return (
                  <div
                    key={key}
                    className="rounded border border-white/5 bg-surface-container-low/40 glass-panel p-4"
                  >
                    <p className="font-headline-lg text-sm font-medium text-white/90">{label}</p>
                    <p className="mt-1 font-data-mono text-2xl text-tertiary">{val.toFixed(1)}</p>
                    <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-container-highest">
                      <div
                        className="h-full rounded-full liquid-fill"
                        style={{ width: `${Math.min(100, (val / 50) * 100)}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
            <p className="mt-3 font-label-sm text-xs text-on-surface-variant leading-relaxed">
              Multiplier applied to final score: {candidate.recruitability.multiplier.toFixed(3)}×
              {signals?.open_to_work_flag && (
                <span className="ml-3 text-tertiary font-medium">✓ Open to work</span>
              )}
              {signals?.notice_period_days != null && (
                <span className="ml-3">Notice: {signals.notice_period_days}d</span>
              )}
            </p>
          </section>
        )}

        {/* ── Reasoning ── */}
        <section className="mb-10">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <span className="material-symbols-outlined text-tertiary">psychology</span>
                Recruiter Reasoning
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-body-md leading-relaxed text-on-surface-variant">{candidate.reasoning}</p>
            </CardContent>
          </Card>
        </section>

        {/* ── Counterfactual ── */}
        {candidate.counterfactual != null &&
          (candidate.counterfactual.top_improvements?.length ?? 0) > 0 && (
          <section className="mb-10">
            <h2 className="mb-4 font-headline-lg text-headline-md text-white">How Could This Candidate Rank Higher?</h2>
            {candidate.counterfactual.summary && (
              <p className="mb-4 text-on-surface-variant font-body-md text-xs italic">{candidate.counterfactual.summary}</p>
            )}
            <div className="grid gap-4 md:grid-cols-3">
              {candidate.counterfactual.top_improvements.map((cf, i) => (
                <Card key={i}>
                  <CardContent className="pt-6 space-y-2">
                    <p className="font-headline-lg text-sm font-medium text-white/90">{cf.change}</p>
                    <p className="font-data-mono text-sm text-tertiary">+{cf.rank_improvement} rank positions</p>
                    {cf.score_delta !== 0 && (
                      <p className="font-data-mono text-xs text-on-surface-variant">
                        Score Δ: {cf.score_delta > 0 ? "+" : ""}{(cf.score_delta * 100).toFixed(1)}%
                      </p>
                    )}
                    <p className="font-label-sm text-xs text-on-surface-variant leading-relaxed">{cf.feasibility}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </section>
        )}

        {/* ── Skills ── */}
        {signals?.skill_assessment_scores && Object.keys(signals.skill_assessment_scores).length > 0 && (
          <section className="mb-10">
            <h2 className="mb-4 font-headline-lg text-headline-md text-white">Skill Assessments</h2>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {Object.entries(signals.skill_assessment_scores).map(([skill, score]) => (
                <div key={skill} className="rounded border border-white/5 bg-surface-container-low/40 glass-panel p-4">
                  <div className="flex items-center justify-between">
                    <span className="font-headline-lg text-sm font-medium text-white/90">{skill}</span>
                    <span className="font-data-mono text-xs text-on-surface-variant">
                      {score.toFixed(0)}/100
                    </span>
                  </div>
                  <div className="mt-2 flex items-center gap-2">
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-container-highest">
                      <div
                        className={cn("h-full rounded-full", trustScoreColor(score))}
                        style={{ width: `${score}%` }}
                      />
                    </div>
                    <span className="font-data-mono text-xs text-white/80">{score.toFixed(0)}</span>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* ── Signal panel ── */}
        {signals && (
          <section className="mb-10">
            <h2 className="mb-4 font-headline-lg text-headline-md text-white">RedroBSignals</h2>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <SignalTile label="Profile Completeness" value={`${signals.profile_completeness_score?.toFixed(0)}%`} />
              <SignalTile label="Recruiter Response Rate" value={`${((signals.recruiter_response_rate ?? 0) * 100).toFixed(0)}%`} />
              <SignalTile
                label="GitHub Activity"
                value={
                  signals.github_activity_score != null && signals.github_activity_score >= 0
                    ? `${signals.github_activity_score.toFixed(0)}/100`
                    : "No public data"
                }
              />
              <SignalTile label="Email Verified" value={signals.verified_email ? "Yes" : "No"} />
              <SignalTile label="Phone Verified" value={signals.verified_phone ? "Yes" : "No"} />
              {signals.last_active_date && (
                <SignalTile label="Last Active" value={signals.last_active_date} />
              )}
              {signals.connection_count != null && (
                <SignalTile label="Connections" value={String(signals.connection_count)} />
              )}
            </div>
          </section>
        )}

        {/* ── Authenticity flags ── */}
        {(candidate.authenticity?.flags?.length ?? 0) > 0 && (
          <section className="mb-10">
            <h2 className="mb-4 font-headline-lg text-headline-md text-error">Authenticity Flags</h2>
            <ul className="space-y-2">
              {candidate.authenticity.flags.map((flag, i) => (
                <li
                  key={i}
                  className="flex items-start gap-2 rounded border border-error/25 bg-error-container/20 p-4 text-xs font-body-md text-white/90"
                >
                  <span className="material-symbols-outlined text-error text-[18px]">warning</span>
                  {flag}
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* ── Confidence detail ── */}
        <section className="mb-10">
          <Card>
            <CardHeader>
              <CardTitle>Confidence Analysis</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-4">
                <ConfidenceBadge confidence={candidate.confidence.label} />
                <span className="font-data-mono text-sm text-white/95">{candidate.confidence.score}/100</span>
              </div>
              {candidate.confidence.explanation && (
                <p className="mt-3 text-body-md text-sm text-on-surface-variant leading-relaxed">
                  {candidate.confidence.explanation}
                </p>
              )}
            </CardContent>
          </Card>
        </section>
      </div>
    </div>
  );
}

function SignalTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-white/5 bg-surface-container-low/40 glass-panel p-3">
      <p className="font-label-sm text-[10px] uppercase tracking-wider text-secondary">{label}</p>
      <p className="mt-1 font-body-md text-xs font-medium text-white/90">{value}</p>
    </div>
  );
}
