"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { rankCandidates, downloadCSV } from "@/lib/api";
import type { RankedCandidateItem } from "@/lib/types";
import { ScorePill, CareerDNABadge, ConfidenceBadge } from "@/components/badges";
import { LoadingSpinner, ErrorState } from "@/components/shared";
import { parseJobDescription, type RequirementSummary } from "@/lib/jd-parser";

const SAMPLE_REQUIREMENTS = [
  { skill: "PyTorch / TensorFlow", criticality: 95, desc: "Production model training and deployment" },
  { skill: "LLM Fine-tuning", criticality: 88, desc: "PEFT, LoRA, instruction tuning" },
  { skill: "MLOps", criticality: 82, desc: "Model serving, monitoring, CI/CD for ML" },
  { skill: "Vector Search / RAG", criticality: 78, desc: "Embeddings, retrieval pipelines" },
  { skill: "Python", criticality: 90, desc: "Primary implementation language" },
];

const DEFAULT_WEIGHTS = {
  capability: 35,
  trajectory: 25,
  recruitability: 20,
  authenticity: 20,
};

export default function IntakePage() {
  const [jd, setJd] = useState(
    "Senior AI Engineer — build and deploy LLM-powered ranking systems. Requires PyTorch, production ML experience, vector search, and MLOps. Must have shipped models serving 1M+ requests. 5+ years experience. No consulting-only backgrounds."
  );
  const [synthesized, setSynthesized] = useState(false);
  const [weights, setWeights] = useState(DEFAULT_WEIGHTS);
  const [hasRisk, setHasRisk] = useState(false);

  const [parsedSummary, setParsedSummary] = useState<RequirementSummary | null>(null);
  const [rankedResults, setRankedResults] = useState<RankedCandidateItem[]>([]);
  const [loadingCandidates, setLoadingCandidates] = useState(false);
  const [errorCandidates, setErrorCandidates] = useState<string | null>(null);

  // Recruiter Controls States
  const [topN, setTopN] = useState<number>(10);
  const [customTopN, setCustomTopN] = useState<string>("");
  const [showCustomTopN, setShowCustomTopN] = useState(false);
  const [sortBy, setSortBy] = useState<string>("overall_match");
  const [minMatch, setMinMatch] = useState<number>(0);
  const [selectedLocations, setSelectedLocations] = useState<string[]>([]);
  const [selectedExperiences, setSelectedExperiences] = useState<string[]>([]);
  const [selectedWorkModes, setSelectedWorkModes] = useState<string[]>([]);

  const [loadingStep, setLoadingStep] = useState(0);

  useEffect(() => {
    let interval: any;
    if (loadingCandidates) {
      setLoadingStep(0);
      interval = setInterval(() => {
        setLoadingStep((prev) => prev + 1);
      }, 800);
    } else {
      setLoadingStep(0);
    }
    return () => clearInterval(interval);
  }, [loadingCandidates]);

  const getLoadingMessage = () => {
    if (loadingStep === 0) return "Analyzing Job Description...";
    if (loadingStep === 1) return "Matching candidates...";
    return "Ranking candidates...";
  };

  const handleSynthesize = () => {
    setSynthesized(true);
    setHasRisk(jd.toLowerCase().includes("consulting") || jd.toLowerCase().includes("10+ years tenure"));
    
    // Parse JD dynamically
    const summary = parseJobDescription(jd);
    setParsedSummary(summary);
    
    // Reset previous candidates state
    setRankedResults([]);
    setErrorCandidates(null);
  };

  const handleFindCandidates = async (overrideTopN?: number) => {
    if (loadingCandidates) return;
    setLoadingCandidates(true);
    setErrorCandidates(null);
    try {
      const decimalWeights = {
        capability: weights.capability / 100,
        trajectory: weights.trajectory / 100,
        recruitability: weights.recruitability / 100,
        authenticity: weights.authenticity / 100,
      };
      
      const queryTopN = overrideTopN !== undefined ? overrideTopN : topN;
      const res = await rankCandidates(decimalWeights, queryTopN, parsedSummary);
      setRankedResults(res.results);
    } catch (err: any) {
      setErrorCandidates(err.message || "Failed to find candidates. Please verify the backend service is active.");
    } finally {
      setLoadingCandidates(false);
    }
  };

  const totalWeight = Object.values(weights).reduce((a, b) => a + b, 0);

  const availableLocations = Array.from(
    new Set(
      rankedResults
        .map((c) => c.location.split(",")[0].trim())
        .filter((l) => l && l !== "Not specified")
    )
  ).slice(0, 8);

  const displayedCandidates = rankedResults
    .filter((c) => {
      const overallMatch = Math.round(c.final_score * 100);
      if (overallMatch < minMatch) return false;

      if (selectedLocations.length > 0) {
        const city = c.location.split(",")[0].trim().toLowerCase();
        const matchesLoc = selectedLocations.some((loc) =>
          city === loc.toLowerCase() || c.location.toLowerCase().includes(loc.toLowerCase())
        );
        if (!matchesLoc) return false;
      }

      if (selectedExperiences.length > 0) {
        const exp = c.years_of_experience;
        const matchesExp = selectedExperiences.some((range) => {
          if (range === "0-2 Years") return exp >= 0 && exp < 2;
          if (range === "2-5 Years") return exp >= 2 && exp < 5;
          if (range === "5-8 Years") return exp >= 5 && exp < 8;
          if (range === "8+ Years") return exp >= 8;
          return false;
        });
        if (!matchesExp) return false;
      }

      if (selectedWorkModes.length > 0) {
        const mode = c.preferred_work_mode ? c.preferred_work_mode.toLowerCase() : "";
        const matchesMode = selectedWorkModes.some((m) => {
          if (m === "Remote") return mode === "remote";
          if (m === "Hybrid") return mode === "flexible" || mode === "hybrid";
          if (m === "Onsite") return mode === "onsite";
          return false;
        });
        if (!matchesMode) return false;
      }

      return true;
    });

  const handleExport = (type: string) => {
    const mapToExport = (list: RankedCandidateItem[]) => {
      return list.map((c) => ({
        candidate_id: c.candidate_id,
        rank: c.rank,
        final_score: c.final_score,
        capability: c.capability,
        trajectory: c.trajectory,
        recruitability: c.recruitability,
        authenticity: c.authenticity,
        confidence: c.confidence,
        reasoning: c.reasoning,
        counterfactual: c.counterfactual,
        career_dna: c.career_dna,
        location: c.location,
        years_of_experience: c.years_of_experience,
        open_to_work: true,
        company: (c.trajectory as any).current_company || "Company",
        title: (c.trajectory as any).current_title || "Engineer",
        notice_period_days: 30,
        response_rate: 0.8,
        github_score: 50,
        career_timeline: [],
        skills: [],
      })) as any[]; // Type assertion to bypass strict CandidateListItem properties if necessary, but fields are populated.
    };

    if (type === "current") {
      downloadCSV(mapToExport(displayedCandidates), "talentgraph-intake-current.csv");
    } else if (type === "top10") {
      downloadCSV(mapToExport(rankedResults.slice(0, 10)), "talentgraph-intake-top10.csv");
    } else if (type === "top20") {
      downloadCSV(mapToExport(rankedResults.slice(0, 20)), "talentgraph-intake-top20.csv");
    } else if (type === "top50") {
      downloadCSV(mapToExport(rankedResults.slice(0, 50)), "talentgraph-intake-top50.csv");
    } else if (type === "top100") {
      downloadCSV(mapToExport(rankedResults.slice(0, 100)), "talentgraph-intake-top100.csv");
    } else if (type === "filtered") {
      downloadCSV(mapToExport(displayedCandidates), "talentgraph-intake-filtered.csv");
    }
  };

  return (
    <div className="mx-auto max-w-container px-margin-mobile py-8 md:px-margin-desktop pt-24 space-y-6">
      <div className="mb-8">
        <p className="font-label-sm text-xs uppercase tracking-wider text-tertiary">Job Intake</p>
        <h1 className="font-headline-lg text-headline-lg text-white mt-1">Requirement Extraction &amp; Signal Mapping</h1>
      </div>

      <div className="grid gap-8 lg:grid-cols-2">
        {/* Left: JD input */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Raw Job Description</CardTitle>
            </CardHeader>
            <CardContent>
              <textarea
                value={jd}
                onChange={(e) => setJd(e.target.value)}
                rows={12}
                className="w-full rounded border border-white/5 bg-surface-container-low/60 etched-input p-4 text-sm focus:outline-none focus:ring-1 focus:ring-tertiary text-white font-body-md"
                placeholder="Paste job description..."
              />
              <Button className="mt-4 w-full" onClick={handleSynthesize}>
                <span className="material-symbols-outlined mr-2 text-base">auto_awesome</span>
                Synthesize Signal
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Dimension Configurator</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {(Object.keys(weights) as (keyof typeof weights)[]).map((dim) => (
                <div key={dim} className="space-y-1">
                  <div className="flex justify-between text-xs capitalize text-on-surface-variant font-label-sm">
                    <span className="text-white/80">{dim}</span>
                    <span className="font-data-mono">{weights[dim]}%</span>
                  </div>
                  <input
                    type="range"
                    min={5}
                    max={50}
                    value={weights[dim]}
                    onChange={(e) => setWeights({ ...weights, [dim]: Number(e.target.value) })}
                    className="w-full accent-tertiary"
                  />
                </div>
              ))}
              <p className={`text-xs font-data-mono pt-2 border-t border-white/5 ${totalWeight === 100 ? "text-tertiary" : "text-error"}`}>
                Total Weight: {totalWeight}% {totalWeight !== 100 && "(should equal 100%)"}
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Right: Extracted requirements & Candidate Matches */}
        <div className="space-y-6">
          {!synthesized ? (
            <div className="flex h-full min-h-[400px] items-center justify-center rounded border border-dashed border-white/10 bg-surface-container-low/20 p-8 text-center font-label-sm text-xs text-on-surface-variant">
              Paste a JD and click Synthesize Signal to extract requirements
            </div>
          ) : (
            <div className="space-y-6">
              {/* Requirement Summary Card */}
              {parsedSummary && (
                <Card className="p-4 space-y-4">
                  <div className="space-y-2">
                    <p className="font-label-sm text-xs text-tertiary uppercase tracking-wider">Requirement Summary</p>
                    <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
                      <div>
                        <span className="text-on-surface-variant font-label-sm">Role</span>
                        <p className="font-headline-lg font-medium text-white/95">{parsedSummary.role}</p>
                      </div>
                      <div>
                        <span className="text-on-surface-variant font-label-sm">Seniority</span>
                        <p className="font-headline-lg font-medium text-white/95">{parsedSummary.seniority}</p>
                      </div>
                      <div>
                        <span className="text-on-surface-variant font-label-sm">Experience</span>
                        <p className="font-headline-lg font-medium text-white/95">{parsedSummary.experience}</p>
                      </div>
                      <div>
                        <span className="text-on-surface-variant font-label-sm">Location</span>
                        <p className="font-headline-lg font-medium text-white/95">
                          {parsedSummary.location} {parsedSummary.remoteHybrid !== "Not specified" && `(${parsedSummary.remoteHybrid})`}
                        </p>
                      </div>
                      <div>
                        <span className="text-on-surface-variant font-label-sm">Employment Type</span>
                        <p className="font-headline-lg font-medium text-white/95">{parsedSummary.employmentType}</p>
                      </div>
                      <div>
                        <span className="text-on-surface-variant font-label-sm">Notice Period</span>
                        <p className="font-headline-lg font-medium text-white/95">{parsedSummary.noticePeriod}</p>
                      </div>
                    </div>
                  </div>

                  <div className="border-t border-white/5 pt-3 space-y-1.5">
                    <p className="font-label-sm text-[10px] text-tertiary uppercase tracking-wider">Scoring Weights Applied</p>
                    <div className="grid grid-cols-4 gap-2 text-xs font-data-mono">
                      <div className="bg-surface-container-low/60 rounded p-1.5 border border-white/5 text-center">
                        <span className="text-on-surface-variant block text-[10px]">Cap</span>
                        <span className="text-white font-medium">{weights.capability}%</span>
                      </div>
                      <div className="bg-surface-container-low/60 rounded p-1.5 border border-white/5 text-center">
                        <span className="text-on-surface-variant block text-[10px]">Traj</span>
                        <span className="text-white font-medium">{weights.trajectory}%</span>
                      </div>
                      <div className="bg-surface-container-low/60 rounded p-1.5 border border-white/5 text-center">
                        <span className="text-on-surface-variant block text-[10px]">Rec</span>
                        <span className="text-white font-medium">{weights.recruitability}%</span>
                      </div>
                      <div className="bg-surface-container-low/60 rounded p-1.5 border border-white/5 text-center">
                        <span className="text-on-surface-variant block text-[10px]">Auth</span>
                        <span className="text-white font-medium">{weights.authenticity}%</span>
                      </div>
                    </div>
                  </div>
                </Card>
              )}

              {/* Warnings */}
              {hasRisk && (
                <div className="relative rounded border border-error/25 bg-error-container/20 p-4">
                  <p className="flex items-center gap-2 font-headline-lg text-sm text-error font-medium">
                    <span className="material-symbols-outlined text-base">warning</span>
                    Rigid tenure filter detected — may exclude high-trajectory candidates
                  </p>
                </div>
              )}

              {/* Extracted Skills Progress timeline */}
              {parsedSummary && parsedSummary.skills.length > 0 && (
                <div className="relative space-y-4">
                  <p className="font-label-sm text-xs text-tertiary uppercase tracking-wider">Extracted Technical Signals</p>
                  <div className="relative">
                    <div className="absolute left-4 top-0 bottom-0 w-px bg-tertiary/20" />
                    <div className="space-y-4 pl-10">
                      {parsedSummary.skills.map((skill, idx) => {
                        const criticality = Math.max(70, 95 - idx * 5);
                        return (
                          <div key={skill} className="relative rounded border border-white/5 bg-surface-container-low/40 glass-panel p-4">
                            <div className="absolute -left-[30px] top-[22px] h-2.5 w-2.5 rounded-full bg-tertiary ring-4 ring-tertiary/20" />
                            <div className="flex items-center justify-between">
                              <span className="font-headline-lg text-sm font-medium text-white/90">{skill}</span>
                              <span className="font-data-mono text-xs text-tertiary">{criticality}% critical</span>
                            </div>
                            <p className="mt-1 text-xs text-on-surface-variant leading-relaxed font-body-md">
                              {skill} implementation and model optimization integration
                            </p>
                            <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-surface-container-highest">
                              <div className="h-full rounded-full liquid-fill" style={{ width: `${criticality}%` }} />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              )}

              {/* Action Button */}
              <Button
                className="w-full font-label-sm text-xs uppercase tracking-wider"
                onClick={() => handleFindCandidates(topN)}
                disabled={loadingCandidates}
              >
                <span className="material-symbols-outlined mr-2 text-base">
                  {loadingCandidates ? "progress_activity" : "search"}
                </span>
                Find Best Candidates
              </Button>

              {/* Loading Indicator */}
              {loadingCandidates && (
                <div className="pt-2">
                  <LoadingSpinner label={getLoadingMessage()} />
                </div>
              )}

              {/* Error Block */}
              {errorCandidates && !loadingCandidates && (
                <div className="pt-2">
                  <ErrorState message={errorCandidates} onRetry={handleFindCandidates} />
                </div>
              )}

              {/* Candidates Results List */}
              {!loadingCandidates && !errorCandidates && rankedResults.length > 0 && (
                <div className="space-y-6 pt-6 border-t border-white/5">
                  <div>
                    <h2 className="font-headline-lg text-headline-md text-white">Top Matching Candidates</h2>
                    <p className="font-label-sm text-xs text-on-surface-variant uppercase tracking-widest mt-1">
                      Ranked by your configured weights · Powered by FHire
                    </p>
                  </div>

                  {/* Recruiter Toolbar Controls */}
                  <div className="rounded border border-white/5 bg-surface-container-low/40 glass-panel p-4 space-y-4">
                    <div className="grid gap-4 md:grid-cols-3">
                      {/* Results Count Selector */}
                      <div className="space-y-1">
                        <label className="text-[10px] text-on-surface-variant uppercase tracking-wider block font-label-sm">
                          Results Count
                        </label>
                        <select
                          value={showCustomTopN ? "custom" : topN}
                          onChange={(e) => {
                            const val = e.target.value;
                            if (val === "custom") {
                              setShowCustomTopN(true);
                            } else {
                              setShowCustomTopN(false);
                              const num = Number(val);
                              setTopN(num);
                              handleFindCandidates(num);
                            }
                          }}
                          className="w-full bg-surface-container-low/60 rounded border border-white/5 p-2 text-xs text-white focus:outline-none focus:ring-1 focus:ring-tertiary"
                        >
                          <option value="10">Top 10</option>
                          <option value="20">Top 20</option>
                          <option value="50">Top 50</option>
                          <option value="100">Top 100</option>
                          <option value="250">Top 250</option>
                          <option value="500">Top 500</option>
                          <option value="custom">Custom...</option>
                        </select>
                        {showCustomTopN && (
                          <div className="flex gap-2 items-center mt-1">
                            <input
                              type="number"
                              placeholder="Count..."
                              value={customTopN}
                              onChange={(e) => setCustomTopN(e.target.value)}
                              className="w-full bg-surface-container-low/60 rounded border border-white/5 p-1 text-xs text-white focus:outline-none focus:ring-1 focus:ring-tertiary"
                            />
                            <Button
                              className="text-[9px] px-2 py-1 h-auto"
                              onClick={() => {
                                const num = Number(customTopN);
                                if (num > 0) {
                                  setTopN(num);
                                  handleFindCandidates(num);
                                }
                              }}
                            >
                              Apply
                            </Button>
                          </div>
                        )}
                      </div>

                      {/* Sort Metric Selector */}
                      <div className="space-y-1">
                        <label className="text-[10px] text-on-surface-variant uppercase tracking-wider block font-label-sm">
                          Sort By
                        </label>
                        <select
                          value={sortBy}
                          onChange={(e) => setSortBy(e.target.value)}
                          className="w-full bg-surface-container-low/60 rounded border border-white/5 p-2 text-xs text-white focus:outline-none focus:ring-1 focus:ring-tertiary"
                        >
                          <option value="overall_match">Overall Match</option>
                          <option value="requirement_match">Requirement Match</option>
                          <option value="capability">Capability Score</option>
                          <option value="trajectory">Trajectory Score</option>
                          <option value="recruitability">Recruitability Score</option>
                          <option value="authenticity">Authenticity Score</option>
                          <option value="experience">Years of Experience</option>
                        </select>
                      </div>

                      {/* Minimum Match Slider */}
                      <div className="space-y-1">
                        <div className="flex justify-between text-[10px] text-on-surface-variant uppercase tracking-wider font-label-sm">
                          <span>Min Match Limit</span>
                          <span className="font-data-mono text-white font-medium">{minMatch}%</span>
                        </div>
                        <input
                          type="range"
                          min="0"
                          max="100"
                          value={minMatch}
                          onChange={(e) => setMinMatch(Number(e.target.value))}
                          className="w-full accent-tertiary mt-2"
                        />
                      </div>
                    </div>

                    {/* Filter Badges Lists */}
                    <div className="space-y-3 pt-2 border-t border-white/5">
                      {/* Location Filter */}
                      {availableLocations.length > 0 && (
                        <div className="space-y-1">
                          <span className="text-[9px] text-on-surface-variant uppercase tracking-wider block font-data-mono">
                            Filter Locations
                          </span>
                          <div className="flex flex-wrap gap-1.5">
                            {availableLocations.map((loc) => {
                              const active = selectedLocations.includes(loc);
                              return (
                                <button
                                  key={loc}
                                  onClick={() => {
                                    if (active) {
                                      setSelectedLocations(selectedLocations.filter((l) => l !== loc));
                                    } else {
                                      setSelectedLocations([...selectedLocations, loc]);
                                    }
                                  }}
                                  className={cn(
                                    "px-2 py-0.5 rounded text-[10px] border transition-colors",
                                    active
                                      ? "bg-tertiary/20 border-tertiary text-tertiary font-medium"
                                      : "bg-surface-container-low/40 border-white/5 text-on-surface-variant hover:border-white/10"
                                  )}
                                >
                                  {loc}
                                </button>
                              );
                            })}
                            {selectedLocations.length > 0 && (
                              <button
                                onClick={() => setSelectedLocations([])}
                                className="px-1.5 py-0.5 rounded text-[10px] bg-error-container/20 border border-error/20 text-error transition-colors"
                              >
                                Clear
                              </button>
                            )}
                          </div>
                        </div>
                      )}

                      <div className="grid gap-4 md:grid-cols-2">
                        {/* Experience Filter */}
                        <div className="space-y-1">
                          <span className="text-[9px] text-on-surface-variant uppercase tracking-wider block font-data-mono">
                            Filter Experience
                          </span>
                          <div className="flex flex-wrap gap-1.5">
                            {["0-2 Years", "2-5 Years", "5-8 Years", "8+ Years"].map((range) => {
                              const active = selectedExperiences.includes(range);
                              return (
                                <button
                                  key={range}
                                  onClick={() => {
                                    if (active) {
                                      setSelectedExperiences(selectedExperiences.filter((r) => r !== range));
                                    } else {
                                      setSelectedExperiences([...selectedExperiences, range]);
                                    }
                                  }}
                                  className={cn(
                                    "px-2 py-0.5 rounded text-[10px] border transition-colors",
                                    active
                                      ? "bg-tertiary/20 border-tertiary text-tertiary font-medium"
                                      : "bg-surface-container-low/40 border-white/5 text-on-surface-variant hover:border-white/10"
                                  )}
                                >
                                  {range}
                                </button>
                              );
                            })}
                          </div>
                        </div>

                        {/* Work Modes Filter */}
                        <div className="space-y-1">
                          <span className="text-[9px] text-on-surface-variant uppercase tracking-wider block font-data-mono">
                            Work Mode Preferred
                          </span>
                          <div className="flex flex-wrap gap-1.5">
                            {["Remote", "Hybrid", "Onsite"].map((mode) => {
                              const active = selectedWorkModes.includes(mode);
                              return (
                                <button
                                  key={mode}
                                  onClick={() => {
                                    if (active) {
                                      setSelectedWorkModes(selectedWorkModes.filter((m) => m !== mode));
                                    } else {
                                      setSelectedWorkModes([...selectedWorkModes, mode]);
                                    }
                                  }}
                                  className={cn(
                                    "px-2 py-0.5 rounded text-[10px] border transition-colors",
                                    active
                                      ? "bg-tertiary/20 border-tertiary text-tertiary font-medium"
                                      : "bg-surface-container-low/40 border-white/5 text-on-surface-variant hover:border-white/10"
                                  )}
                                >
                                  {mode}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Export Dropdown */}
                    <div className="flex justify-end pt-2 border-t border-white/5">
                      <select
                        onChange={(e) => {
                          const val = e.target.value;
                          if (val) {
                            handleExport(val);
                            e.target.value = "";
                          }
                        }}
                        className="bg-tertiary/10 border border-tertiary/20 text-tertiary rounded px-3 py-1.5 text-[10px] focus:outline-none font-label-sm uppercase tracking-wider cursor-pointer"
                      >
                        <option value="" disabled selected>CSV Export Actions...</option>
                        <option value="current">Export Current Results ({displayedCandidates.length})</option>
                        <option value="top10">Export Top 10</option>
                        <option value="top20">Export Top 20</option>
                        <option value="top50">Export Top 50</option>
                        <option value="top100">Export Top 100</option>
                        <option value="filtered">Export All Filtered</option>
                      </select>
                    </div>
                  </div>

                  {/* Candidates Cards Grid List */}
                  {displayedCandidates.length === 0 ? (
                    <div className="text-center py-8 rounded border border-white/5 bg-surface-container-low/20 text-xs text-on-surface-variant">
                      No candidates match your current filter criteria
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {displayedCandidates.map((c, i) => {
                        const rank = c.rank;
                        const borderAccent = rank === 1
                          ? "border-l-2 border-l-tertiary"
                          : (rank === 2 || rank === 3)
                            ? "border-l-2 border-l-white/60"
                            : "";

                        return (
                          <div
                            key={c.candidate_id}
                            className={cn(
                              "rounded border border-white/5 bg-surface-container-low/40 glass-panel p-4 hover:border-tertiary/50 hover:bg-surface-container-low/60 transition-all duration-300 space-y-4",
                              borderAccent
                            )}
                          >
                            <div className="flex items-start justify-between">
                              <div className="space-y-1.5">
                                <div className="flex items-center gap-2">
                                  <span className="font-data-mono text-xl font-bold text-tertiary">#{rank}</span>
                                  <span className="font-data-mono text-xs text-on-surface-variant">{c.candidate_id}</span>
                                </div>
                                <div className="flex flex-wrap gap-1.5">
                                  <CareerDNABadge dna={c.career_dna} />
                                  <ConfidenceBadge confidence={c.confidence.label} />
                                </div>
                              </div>
                              <ScorePill score={c.final_score} />
                            </div>

                            {/* Dual overall and requirement match display values */}
                            <div className="grid grid-cols-2 gap-4 bg-surface-container-low/30 rounded border border-white/5 p-3 text-xs">
                              <div>
                                <span className="text-[10px] text-on-surface-variant block uppercase tracking-wider font-label-sm">
                                  Overall Match
                                </span>
                                <span className="text-base font-bold font-data-mono text-secondary">
                                  {Math.round(c.final_score * 100)}%
                                </span>
                              </div>
                              <div>
                                <span className="text-[10px] text-on-surface-variant block uppercase tracking-wider font-label-sm">
                                  Requirement Match
                                </span>
                                <span className="text-base font-bold font-data-mono text-tertiary">
                                  {c.requirement_match ? `${Math.round(c.requirement_match.score)}%` : "100%"}
                                </span>
                              </div>
                            </div>

                            {/* Scoring dimension components metrics info */}
                            <div className="font-data-mono text-[9px] text-on-surface-variant flex flex-wrap gap-x-2 gap-y-1 border-t border-b border-white/5 py-2 justify-between">
                              <span>Cap <strong className="text-white">{c.capability.toFixed(0)}</strong></span>
                              <span>Traj <strong className="text-white">{c.trajectory.score.toFixed(0)}</strong></span>
                              <span>Rec <strong className="text-white">{c.recruitability.score.toFixed(0)}</strong></span>
                              <span>Auth <strong className="text-white">{c.authenticity.score.toFixed(0)}</strong></span>
                              <span>Exp <strong className="text-white">{c.years_of_experience.toFixed(1)}y</strong></span>
                              <span>Loc <strong className="text-white">{c.location.split(",")[0].trim()}</strong></span>
                            </div>

                            {/* Explanation match signals checks list */}
                            <div className="space-y-2">
                              <span className="font-data-mono text-[9px] text-tertiary uppercase tracking-wider block">
                                Matched because
                              </span>
                              <div className="flex flex-wrap gap-x-3 gap-y-1.5 text-xs">
                                {c.requirement_match?.matched_skills && c.requirement_match.matched_skills.map((skill) => (
                                  <span key={skill} className="flex items-center gap-1 text-emerald-400 font-body-md text-[11px]">
                                    <span className="material-symbols-outlined text-[10px] text-emerald-400 font-bold">check</span>
                                    {skill}
                                  </span>
                                ))}
                                
                                {c.requirement_match?.experience_matched && (
                                  <span className="flex items-center gap-1 text-emerald-400 font-body-md text-[11px]">
                                    <span className="material-symbols-outlined text-[10px] font-bold">check</span>
                                    {c.years_of_experience.toFixed(1)}y Experience
                                  </span>
                                )}

                                {c.requirement_match?.location_matched && (
                                  <span className="flex items-center gap-1 text-emerald-400 font-body-md text-[11px]">
                                    <span className="material-symbols-outlined text-[10px] font-bold">check</span>
                                    {c.location.split(",")[0].trim()}
                                  </span>
                                )}
                                
                                {c.requirement_match?.missing_skills && c.requirement_match.missing_skills.map((skill) => (
                                  <span key={skill} className="flex items-center gap-1 text-on-surface-variant font-body-md text-[11px] opacity-60">
                                    <span className="text-[12px] font-bold text-error leading-none">•</span>
                                    {skill}
                                  </span>
                                ))}
                              </div>

                              <p className="text-xs text-on-surface-variant italic font-body-md leading-relaxed line-clamp-2 border-t border-dashed border-white/5 pt-1.5">
                                {c.reasoning}
                              </p>
                            </div>

                            <div className="pt-2">
                              {(() => {
                                const contextObj = {
                                  weights: {
                                    capability: weights.capability / 100,
                                    trajectory: weights.trajectory / 100,
                                    recruitability: weights.recruitability / 100,
                                    authenticity: weights.authenticity / 100,
                                  },
                                  requirements: parsedSummary,
                                };
                                const contextStr = btoa(encodeURIComponent(JSON.stringify(contextObj)).replace(/%([0-9A-F]{2})/g, (match, p1) => {
                                  return String.fromCharCode(parseInt(p1, 16));
                                }));
                                return (
                                  <Link href={`/candidate/${c.candidate_id}?from=intake&context=${encodeURIComponent(contextStr)}`} passHref legacyBehavior>
                                    <Button variant="outline" className="w-full text-xs font-label-sm py-1.5">
                                      View Candidate
                                    </Button>
                                  </Link>
                                );
                              })()}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
