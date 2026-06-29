"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { SignalField } from "@/components/signal-field";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getHealth, triggerRank, ApiError } from "@/lib/api";

type DemoPhase = "idle" | "checking" | "scoring" | "selecting" | "done" | "error";

export default function DemoPage() {
  const router = useRouter();
  const [phase, setPhase] = useState<DemoPhase>("idle");
  const [progress, setProgress] = useState(0);
  const [statusMsg, setStatusMsg] = useState("");
  const [poolSize, setPoolSize] = useState<number | null>(null);
  const [errorMsg, setErrorMsg] = useState("");

  // Check pool size on mount
  useEffect(() => {
    getHealth()
      .then((h) => setPoolSize(h.ranked_pool_size))
      .catch(() => {/* non-critical */});
  }, []);

  const handleRun = async () => {
    setPhase("checking");
    setProgress(0);
    setErrorMsg("");

    // Check health first
    try {
      const health = await getHealth();
      if (!health.distributions_loaded) {
        setErrorMsg("Backend distributions not loaded. Run precompute.py first.");
        setPhase("error");
        return;
      }
      setStatusMsg(
        health.ranked_pool_size > 0
          ? `Pool already has ${health.ranked_pool_size.toLocaleString()} candidates — triggering fresh re-rank…`
          : "Triggering full ranking pipeline…"
      );
    } catch (e) {
      setErrorMsg(
        e instanceof ApiError
          ? e.message
          : "Cannot reach backend. Ensure the FastAPI server is running."
      );
      setPhase("error");
      return;
    }

    setPhase("scoring");
    const scoringInterval = setInterval(() => {
      setProgress((p) => Math.min(p + 1, 55));
    }, 300);

    try {
      // Trigger ranking (may take a while for 100k candidates)
      const result = await triggerRank();
      clearInterval(scoringInterval);
      setProgress(60);
      setPhase("selecting");
      setStatusMsg(`Scored ${result.total_scored.toLocaleString()} candidates…`);

      const selectInterval = setInterval(() => {
        setProgress((p) => Math.min(p + 4, 100));
      }, 60);

      await new Promise((r) => setTimeout(r, 1500));
      clearInterval(selectInterval);
      setProgress(100);
      setPhase("done");
      setStatusMsg(
        `Complete — ${result.total_scored.toLocaleString()} ranked, ${result.total_disqualified.toLocaleString()} disqualified`
      );

      setTimeout(() => router.push("/rankings"), 900);
    } catch (e) {
      clearInterval(scoringInterval);
      setErrorMsg(
        e instanceof ApiError
          ? e.message
          : "Ranking pipeline failed. Check the backend logs."
      );
      setPhase("error");
    }
  };

  return (
    <div className="relative flex min-h-[80vh] items-center justify-center overflow-hidden pt-24">
      <SignalField opacity={0.35} />

      <div className="relative z-10 mx-auto max-w-lg px-margin-mobile text-center md:px-margin-desktop">
        <Card className="backdrop-blur-xl">
          <CardHeader className="space-y-1">
            <CardTitle className="font-headline-lg text-headline-md text-white">Live Ranking Demo</CardTitle>
            <p className="font-body-md text-xs text-on-surface-variant leading-relaxed">
              Run the full 4-dimension scoring pipeline against the real candidate dataset.
            </p>
          </CardHeader>
          <CardContent className="space-y-6">
            {phase === "idle" && (
              <>
                <div className="rounded border border-white/5 bg-surface-container-low/40 glass-panel p-4 text-left font-data-mono text-xs text-on-surface-variant leading-relaxed space-y-1">
                  <p>
                    •{" "}
                    {poolSize != null
                      ? `${poolSize.toLocaleString()} candidates currently in ranked pool`
                      : "Connecting to backend…"}
                  </p>
                  <p>• 4-dimension scoring model (capability · trajectory · recruitability · authenticity)</p>
                  <p>• Semantic similarity via pre-computed embeddings</p>
                  <p>• Disqualifier + authenticity honeypot detection</p>
                </div>
                <Button size="lg" className="w-full" onClick={handleRun}>
                  <span className="material-symbols-outlined mr-2 text-base">play_arrow</span>
                  Run Full Ranking Pipeline
                </Button>
              </>
            )}

            {phase === "checking" && (
              <div className="space-y-4 py-4">
                <p className="font-label-sm text-xs uppercase tracking-wider text-tertiary">
                  Checking backend…
                </p>
                <div className="flex justify-center">
                  <div className="h-6 w-6 animate-spin rounded-full border-2 border-tertiary border-t-transparent" />
                </div>
              </div>
            )}

            {(phase === "scoring" || phase === "selecting" || phase === "done") && (
              <div className="space-y-4 py-4">
                <div className="h-2 overflow-hidden rounded-full bg-surface-container-highest">
                  <div
                    className="h-full rounded-full liquid-fill transition-all duration-300"
                    style={{ width: `${progress}%` }}
                  />
                </div>
                <p className="font-label-sm text-xs uppercase tracking-wider text-tertiary">
                  {phase === "scoring" && "Scoring candidates…"}
                  {phase === "selecting" && statusMsg}
                  {phase === "done" && statusMsg}
                </p>
                {phase !== "done" && (
                  <div className="flex justify-center">
                    <div className="h-6 w-6 animate-spin rounded-full border-2 border-tertiary border-t-transparent" />
                  </div>
                )}
                {phase === "done" && (
                  <p className="font-data-mono text-xs text-on-surface-variant">Redirecting to rankings…</p>
                )}
              </div>
            )}

            {phase === "error" && (
              <div className="space-y-4 py-4">
                <p className="font-label-sm text-xs text-error">{errorMsg}</p>
                <div className="flex justify-center gap-2">
                  <Button
                    variant="outline"
                    onClick={() => {
                      setPhase("idle");
                      setErrorMsg("");
                      setProgress(0);
                    }}
                  >
                    Retry
                  </Button>
                  <Button asChild variant="ghost">
                    <a href="/rankings">Go to Rankings</a>
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
