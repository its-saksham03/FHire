"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { SignalField } from "@/components/signal-field";
import { ErrorState, LoadingSpinner } from "@/components/shared";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, getStats } from "@/lib/api";
import type { Stats } from "@/lib/types";

const DNA_COLORS = ["#7dd3fc", "#cbd5e1", "#334155", "#0c4a6e", "#f87171"];
const CONF_COLORS = ["#7dd3fc", "#cbd5e1", "#f87171"];

function ConstellationChart({ data }: { data: Array<{ range: string; count: number }> }) {
  const dots = useMemo(
    () =>
      Array.from({ length: 80 }, () => ({
        x: 10 + Math.random() * 80,
        y: 10 + Math.random() * 80,
        delay: Math.random() * 4,
        size: 2 + Math.random() * 4,
      })),
    []
  );

  return (
    <div className="relative h-64 w-full">
      <svg className="absolute inset-0 h-full w-full opacity-20" viewBox="0 0 100 100">
        <path d="M0,50 Q25,30 50,50 T100,50" fill="none" stroke="#7dd3fc" strokeWidth="0.5" />
        <path d="M0,70 Q50,40 100,70" fill="none" stroke="#cbd5e1" strokeWidth="0.5" />
      </svg>
      {dots.map((d, i) => (
        <div
          key={i}
          className="absolute rounded-full bg-tertiary animate-pulse-soft"
          style={{
            left: `${d.x}%`,
            top: `${d.y}%`,
            width: d.size,
            height: d.size,
            animationDelay: `${d.delay}s`,
          }}
        />
      ))}
      <div className="absolute bottom-2 left-2 font-data-mono text-[10px] text-on-surface-variant">
        {data.map((d) => `${d.range}: ${d.count}`).join(" · ")}
      </div>
    </div>
  );
}

export default function AnalyticsPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setStats(await getStats());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load analytics");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <div className="mx-auto max-w-container px-margin-mobile py-8 md:px-margin-desktop pt-24">
        <LoadingSpinner label="Computing analytics..." />
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="mx-auto max-w-container px-margin-mobile py-8 md:px-margin-desktop pt-24">
        <ErrorState message={error ?? "No data"} onRetry={load} />
      </div>
    );
  }

  // Transform backend dicts to chart-friendly arrays
  const scoreDistribution = Object.entries(stats.score_buckets).map(([range, count]) => ({
    range,
    count,
  }));

  const dnaDistribution = Object.entries(stats.dna_distribution).map(([name, value]) => ({
    name,
    value,
  }));

  const confidenceDistribution = Object.entries(stats.confidence_distribution).map(
    ([name, value]) => ({ name, value })
  );

  const locationDistribution = stats.location_distribution ?? [];
  const noticePeriodDistribution = stats.notice_period_distribution ?? [];

  // Compute mean score from score buckets
  const bucketMidpoints: Record<string, number> = {
    "0.0-0.2": 0.1,
    "0.2-0.4": 0.3,
    "0.4-0.6": 0.5,
    "0.6-0.8": 0.7,
    "0.8-1.0": 0.9,
  };
  const totalForAvg = scoreDistribution.reduce((s, b) => s + b.count, 0);
  const avgScore =
    totalForAvg > 0
      ? scoreDistribution.reduce(
          (s, b) => s + (bucketMidpoints[b.range] ?? 0.5) * b.count,
          0
        ) / totalForAvg
      : 0;

  const highConfidenceCount = stats.confidence_distribution["High"] ?? 0;
  const shortNoticeCount =
    noticePeriodDistribution.find((n) => n.range.includes("0–15"))?.count ?? 0;

  return (
    <div className="mx-auto max-w-container px-margin-mobile py-8 md:px-margin-desktop space-y-stack-md pt-24">
      {/* Hero banner */}
      <section className="relative mb-8 overflow-hidden rounded border border-white/5 bg-surface-container-low/40 glass-panel p-8">
        <SignalField opacity={0.15} />
        <div className="relative z-10 space-y-3">
          <p className="font-label-sm text-xs uppercase tracking-wider text-tertiary">
            Analytics
          </p>
          <h1 className="font-headline-lg text-headline-lg text-white">Pipeline Intelligence</h1>
          <p className="max-w-2xl italic text-body-lg text-on-surface-variant font-body-md">
            &ldquo;{stats.total_ranked.toLocaleString()} candidates scored — mean composite{" "}
            {(avgScore * 100).toFixed(1)}%.
            {stats.disqualified_count > 0 &&
              ` ${stats.disqualified_count.toLocaleString()} disqualified.`}
            &rdquo;
          </p>
          <div className="mt-6 flex flex-wrap gap-8 pt-4">
            <Stat label="Total Scored" value={stats.total_ranked.toLocaleString()} />
            <Stat label="Disqualified" value={stats.disqualified_count.toLocaleString()} />
            <Stat label="High Confidence" value={highConfidenceCount.toLocaleString()} />
            <Stat
              label="Open Pipeline"
              value={shortNoticeCount.toLocaleString()}
              sub="≤15d notice"
            />
            <Stat label="Open to Work" value={stats.open_to_work_count.toLocaleString()} />
          </div>
        </div>
      </section>

      {/* Average dimension scores */}
      <section className="mb-8 grid gap-4 sm:grid-cols-4">
        {(
          [
            { label: "Avg Capability", value: stats.avg_capability },
            { label: "Avg Trajectory", value: stats.avg_trajectory },
            { label: "Avg Recruitability", value: stats.avg_recruitability },
            { label: "Avg Authenticity", value: stats.avg_authenticity },
          ] as const
        ).map(({ label, value }) => (
          <div
            key={label}
            className="rounded border border-white/5 bg-surface-container-low/40 glass-panel p-4"
          >
            <p className="font-label-sm text-[10px] uppercase tracking-wider text-secondary">
              {label}
            </p>
            <p className="mt-1 font-headline-lg text-2xl font-bold text-tertiary">{value.toFixed(1)}</p>
            <div className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-surface-container-highest">
              <div className="h-full rounded-full liquid-fill" style={{ width: `${value}%` }} />
            </div>
          </div>
        ))}
      </section>

      <div className="grid gap-6 lg:grid-cols-12">
        {/* Score distribution */}
        <Card className="lg:col-span-8">
          <CardHeader>
            <CardTitle>Score Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <ConstellationChart data={scoreDistribution} />
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={scoreDistribution}>
                <XAxis dataKey="range" tick={{ fill: "#94a3b8", fontSize: 10, fontFamily: "JetBrains Mono" }} />
                <YAxis tick={{ fill: "#94a3b8", fontSize: 10, fontFamily: "JetBrains Mono" }} />
                <Tooltip contentStyle={{ background: "#111417", border: "1px solid rgba(255,255,255,0.06)", borderRadius: "4px" }} />
                <Bar dataKey="count" fill="#7dd3fc" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Career DNA pie */}
        <Card className="lg:col-span-4">
          <CardHeader>
            <CardTitle>Career DNA Mix</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={dnaDistribution}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={80}
                >
                  {dnaDistribution.map((_, i) => (
                    <Cell key={i} fill={DNA_COLORS[i % DNA_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ background: "#111417", border: "1px solid rgba(255,255,255,0.06)", borderRadius: "4px" }} />
              </PieChart>
            </ResponsiveContainer>
            <div className="mt-4 space-y-1">
              {dnaDistribution.map((d, i) => (
                <div key={d.name} className="flex items-center gap-2 font-label-sm text-[11px] text-on-surface-variant">
                  <div
                    className="h-2 w-2 rounded-full"
                    style={{ background: DNA_COLORS[i % DNA_COLORS.length] }}
                  />
                  {d.name}: {d.value.toLocaleString()}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Location bar chart */}
        {locationDistribution.length > 0 && (
          <Card className="lg:col-span-7">
            <CardHeader>
              <CardTitle>Top Cities</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={locationDistribution} layout="vertical">
                  <XAxis type="number" tick={{ fill: "#94a3b8", fontSize: 10, fontFamily: "JetBrains Mono" }} />
                  <YAxis
                    dataKey="city"
                    type="category"
                    width={110}
                    tick={{ fill: "#94a3b8", fontSize: 10, fontFamily: "JetBrains Mono" }}
                  />
                  <Tooltip contentStyle={{ background: "#111417", border: "1px solid rgba(255,255,255,0.06)", borderRadius: "4px" }} />
                  <Bar dataKey="count" fill="#cbd5e1" radius={[0, 2, 2, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        )}

        {/* Notice period */}
        {noticePeriodDistribution.length > 0 && (
          <Card className="lg:col-span-5">
            <CardHeader>
              <CardTitle>Notice Period Distribution</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={noticePeriodDistribution}>
                  <XAxis dataKey="range" tick={{ fill: "#94a3b8", fontSize: 10, fontFamily: "JetBrains Mono" }} />
                  <YAxis tick={{ fill: "#94a3b8", fontSize: 10, fontFamily: "JetBrains Mono" }} />
                  <Tooltip contentStyle={{ background: "#111417", border: "1px solid rgba(255,255,255,0.06)", borderRadius: "4px" }} />
                  <Bar dataKey="count" fill="#7dd3fc" radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
              <p className="mt-3 font-label-sm text-xs text-on-surface-variant leading-relaxed">
                Avg notice: {stats.avg_notice_period_days.toFixed(0)} days
              </p>
            </CardContent>
          </Card>
        )}

        {/* Confidence pie */}
        <Card className="lg:col-span-4">
          <CardHeader>
            <CardTitle>Confidence Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={confidenceDistribution}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={70}
                >
                  {confidenceDistribution.map((_, i) => (
                    <Cell key={i} fill={CONF_COLORS[i % CONF_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ background: "#111417", border: "1px solid rgba(255,255,255,0.06)", borderRadius: "4px" }} />
              </PieChart>
            </ResponsiveContainer>
            <div className="mt-4 space-y-1">
              {confidenceDistribution.map((d, i) => (
                <div key={d.name} className="flex items-center gap-2 font-label-sm text-[11px] text-on-surface-variant">
                  <div
                    className="h-2 w-2 rounded-full"
                    style={{ background: CONF_COLORS[i % CONF_COLORS.length] }}
                  />
                  {d.name}: {d.value.toLocaleString()}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Open to work stats */}
        <Card className="lg:col-span-8">
          <CardHeader>
            <CardTitle>Availability Overview</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="space-y-1">
                <p className="font-label-sm text-[10px] uppercase tracking-wider text-secondary">
                  Open to Work
                </p>
                <p className="font-headline-lg text-3xl font-bold text-tertiary">
                  {stats.open_to_work_count.toLocaleString()}
                </p>
                <p className="font-label-sm text-[10px] text-on-surface-variant">
                  {stats.total_ranked > 0
                    ? `${((stats.open_to_work_count / stats.total_ranked) * 100).toFixed(1)}% of pool`
                    : ""}
                </p>
              </div>
              <div className="space-y-1">
                <p className="font-label-sm text-[10px] uppercase tracking-wider text-secondary">
                  Avg Notice Period
                </p>
                <p className="font-headline-lg text-3xl font-bold text-tertiary">
                  {stats.avg_notice_period_days.toFixed(0)}d
                </p>
              </div>
              <div className="space-y-1">
                <p className="font-label-sm text-[10px] uppercase tracking-wider text-secondary">
                  ≤15d Notice
                </p>
                <p className="font-headline-lg text-3xl font-bold text-tertiary">
                  {shortNoticeCount.toLocaleString()}
                </p>
                <p className="font-label-sm text-[10px] text-on-surface-variant">immediate availability</p>
              </div>
            </div>
            <p className="italic text-xs text-on-surface-variant font-body-md leading-relaxed pt-2 border-t border-white/5">
              Most hiring friction comes from consulting-only DNA and title misalignment — not raw skill gaps.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="space-y-1">
      <p className="font-label-sm text-[10px] uppercase tracking-wider text-secondary">{label}</p>
      <p className="font-headline-lg text-3xl font-bold text-tertiary">{value}</p>
      {sub && <p className="font-label-sm text-[10px] text-on-surface-variant">{sub}</p>}
    </div>
  );
}
