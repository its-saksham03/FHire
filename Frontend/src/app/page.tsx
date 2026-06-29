"use client";

import Link from "next/link";
import { SignalField } from "@/components/signal-field";
import { Button } from "@/components/ui/button";
import { useFadeInUp } from "@/components/shared";

const DIMENSIONS = [
  {
    num: "01",
    icon: "psychology",
    title: "Capability",
    question: "Can they do the job?",
    description:
      "Production ML depth, not keyword density. We weight verified skill assessments, shipping history, and role-relevant stack exposure over resume inflation.",
  },
  {
    num: "02",
    icon: "trending_up",
    title: "Trajectory",
    question: "Are they growing in the right direction?",
    description:
      "Career velocity toward AI engineering — tenure patterns, seniority progression, and whether each move compounds ML competency or dilutes it.",
  },
  {
    num: "03",
    icon: "bolt",
    title: "Recruitability",
    question: "Can we actually hire them?",
    description:
      "Notice period, open-to-work signals, response rates, and geographic fit — because the best candidate you can't close isn't a hire.",
  },
  {
    num: "04",
    icon: "verified",
    title: "Authenticity",
    question: "Should we trust this profile?",
    description:
      "Title-skill alignment, endorsement patterns, profile completeness, and honeypot detection — filtering profiles that look good on paper but fail recruiter sniff tests.",
  },
];

export default function LandingPage() {
  const containerRef = useFadeInUp();

  return (
    <div ref={containerRef}>
      {/* Hero */}
      <section className="relative flex min-h-[85vh] items-center justify-center overflow-hidden">
        <SignalField opacity={0.3} />
        <div className="relative z-10 mx-auto max-w-container px-margin-mobile py-20 text-center md:px-margin-desktop space-y-stack-md">
          <div className="fade-in-up inline-flex items-center gap-2 px-3 py-1 glass-panel rounded border border-white/10">
            <span className="material-symbols-outlined text-tertiary text-[14px]" style={{ fontVariationSettings: "'FILL' 1" }}>ac_unit</span>
            <span className="font-data-mono text-[10px] uppercase tracking-[0.2em] text-tertiary/80">Intelligence System Active</span>
          </div>
          <h1 className="fade-in-up font-headline-xl text-headline-xl text-white md:text-[56px] leading-tight tracking-tighter">
            AI Talent Intelligence for
            <br />
            <span className="text-tertiary">Modern Recruitment</span>
          </h1>
          <p className="fade-in-up mx-auto max-w-2xl text-body-lg text-on-surface-variant font-body-md leading-relaxed">
            Discover, rank, and analyze over 100,000 candidates using AI-powered scoring, authenticity verification, and deep capability mapping.
          </p>
          <div className="fade-in-up mt-10 flex flex-wrap justify-center gap-4 pt-4">
            <Button asChild size="lg">
              <Link href="/rankings" className="flex items-center gap-2">
                Explore Candidates
                <span className="material-symbols-outlined text-[16px]">arrow_forward</span>
              </Link>
            </Button>
            <Button asChild variant="outline" size="lg">
              <Link href="/analytics">View Analytics</Link>
            </Button>
          </div>
        </div>
      </section>

      {/* Dimensions */}
      <section className="relative border-t border-white/5 bg-surface-container-lowest/40 py-24">
        <div className="absolute left-1/2 top-0 hidden h-full w-px -translate-x-1/2 bg-tertiary/10 md:block" />
        <div className="mx-auto max-w-container px-margin-mobile md:px-margin-desktop">
          <div className="mb-16 text-center">
            <p className="font-label-sm text-xs uppercase tracking-widest text-secondary">
              Four dimensions of hire quality
            </p>
            <h2 className="mt-3 font-headline-lg text-headline-lg text-white">How elite recruiters actually think</h2>
          </div>
          <div className="space-y-8">
            {DIMENSIONS.map((dim, i) => (
              <div
                key={dim.title}
                className={`fade-in-up dimension-card flex flex-col gap-6 md:flex-row md:items-center ${
                  i % 2 === 1 ? "md:flex-row-reverse" : ""
                }`}
              >
                <div className="flex-1 space-y-2">
                  <span className="inline-flex items-center gap-2 rounded border border-tertiary/30 bg-tertiary/5 px-2.5 py-0.5 font-label-sm text-[10px] uppercase tracking-widest text-tertiary">
                    Dimension {dim.num}
                  </span>
                  <h3 className="mt-4 font-headline-lg text-xl text-white/90">{dim.title}</h3>
                  <p className="font-label-sm text-xs text-secondary/90 tracking-wide uppercase">{dim.question}</p>
                  <p className="text-body-md text-on-surface-variant leading-relaxed">{dim.description}</p>
                </div>
                <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded border border-white/5 bg-surface-container-highest/30 glass-panel">
                  <span className="material-symbols-outlined text-3xl text-tertiary">{dim.icon}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="relative overflow-hidden py-24">
        <SignalField opacity={0.1} scale={1.2} rotate={180} />
        <div className="relative z-10 mx-auto max-w-container px-margin-mobile text-center md:px-margin-desktop space-y-4">
          <h2 className="font-headline-lg text-headline-lg text-white">Ready to see who ranks?</h2>
          <p className="text-body-lg text-on-surface-variant font-body-md">
            100,000 candidates scored. Four dimensions. One hiring decision.
          </p>
          <div className="pt-4">
            <Button asChild size="lg">
              <Link href="/rankings">Explore Rankings</Link>
            </Button>
          </div>
        </div>
      </section>
    </div>
  );
}
