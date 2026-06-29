"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { CareerDNABadge, ConfidenceBadge, ScorePill } from "@/components/badges";
import { SignalField } from "@/components/signal-field";
import { ErrorState, LoadingSpinner, TrajectorySparkline } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { ApiError, getCandidates, getLocations, getExportURL } from "@/lib/api";
import type { CandidateListItem, CandidateQueryParams, CareerDNA, Confidence } from "@/lib/types";
import { getCity } from "@/lib/utils";

const PAGE_SIZE = Number(process.env.NEXT_PUBLIC_PAGE_SIZE ?? 50);

const ALL_DNA: CareerDNA[] = [
  "Startup Builder",
  "Scale Expert",
  "Product Engineer",
  "Research Specialist",
  "Consulting Only",
];

const ALL_CONFIDENCE: Confidence[] = ["High", "Medium", "Low"];

export default function RankingsPage() {
  const router = useRouter();

  // ── Data state ─────────────────────────────────────────────────────────────
  const [candidates, setCandidates] = useState<CandidateListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [cursor, setCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ── Filter state ───────────────────────────────────────────────────────────
  const [search, setSearch] = useState("");
  const [location, setLocation] = useState("all");
  const [openToWork, setOpenToWork] = useState(false);
  const [confidence, setConfidence] = useState<string>("all");
  const [selectedDNA, setSelectedDNA] = useState<Set<CareerDNA>>(new Set());
  const [minScore, setMinScore] = useState(0);

  // ── Sort state ─────────────────────────────────────────────────────────────
  const [sortBy, setSortBy] = useState<CandidateQueryParams["sort_by"]>("rank");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  // ── UI state ───────────────────────────────────────────────────────────────
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [locations, setLocations] = useState<string[]>([]);
  const [logLine, setLogLine] = useState("Engine idle — awaiting signal...");

  // Debounce search input
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [debouncedSearch, setDebouncedSearch] = useState("");

  useEffect(() => {
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => setDebouncedSearch(search), 350);
    return () => { if (searchTimer.current) clearTimeout(searchTimer.current); };
  }, [search]);

  // ── Fetch locations once ───────────────────────────────────────────────────
  useEffect(() => {
    getLocations().then(setLocations).catch(() => {/* non-critical */});
  }, []);

  // ── Abort Controller Ref ───────────────────────────────────────────────────
  const abortControllerRef = useRef<AbortController | null>(null);

  // ── Load first cursor slice ────────────────────────────────────────────────
  const loadFirstCursor = useCallback(async () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    setLoading(true);
    setError(null);
    setCandidates([]);
    setCursor(null);
    setHasMore(false);

    try {
      const params: CandidateQueryParams = {
        limit: PAGE_SIZE,
        cursor: null,
        ...(debouncedSearch ? { search: debouncedSearch } : {}),
        ...(location !== "all" ? { location } : {}),
        ...(confidence !== "all" ? { confidence } : {}),
        ...(selectedDNA.size === 1 ? { career_dna: [...selectedDNA][0] } : {}),
        ...(openToWork ? { open_to_work: true } : {}),
        ...(minScore > 0 ? { min_score: minScore / 100 } : {}),
        sort_by: sortBy,
        sort_dir: sortDir,
      };

      const res = await getCandidates(params, abortControllerRef.current.signal);
      setCandidates(res.items ?? res.results ?? []);
      setTotal(res.total);
      setCursor(res.next_cursor ?? null);
      setHasMore(res.has_more ?? false);
      setLogLine(
        res.total > 0
          ? `Ranked ${res.total.toLocaleString()} candidates`
          : "No candidates match current filters"
      );
    } catch (e) {
      if (e instanceof Error && e.name === "AbortError") {
        return; // Ignore canceled request
      }
      setError(e instanceof ApiError ? e.message : "Failed to load rankings");
      setLogLine("Error loading rankings");
    } finally {
      setLoading(false);
    }
  }, [debouncedSearch, location, confidence, selectedDNA, openToWork, minScore, sortBy, sortDir]);

  // Reset/Load when filters or sort change
  useEffect(() => {
    loadFirstCursor();
  }, [loadFirstCursor]);

  // Cleanup abort controller on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) abortControllerRef.current.abort();
    };
  }, []);

  // ── Load next cursor slice ─────────────────────────────────────────────────
  const loadNextCursor = useCallback(async () => {
    if (loadingMore || !hasMore || !cursor) return;
    setLoadingMore(true);
    try {
      const params: CandidateQueryParams = {
        limit: PAGE_SIZE,
        cursor: cursor,
        ...(debouncedSearch ? { search: debouncedSearch } : {}),
        ...(location !== "all" ? { location } : {}),
        ...(confidence !== "all" ? { confidence } : {}),
        ...(selectedDNA.size === 1 ? { career_dna: [...selectedDNA][0] } : {}),
        ...(openToWork ? { open_to_work: true } : {}),
        ...(minScore > 0 ? { min_score: minScore / 100 } : {}),
        sort_by: sortBy,
        sort_dir: sortDir,
      };

      const res = await getCandidates(params);
      const newItems = res.items ?? res.results ?? [];
      setCandidates((prev) => [...prev, ...newItems]);
      setCursor(res.next_cursor ?? null);
      setHasMore(res.has_more ?? false);
      setLogLine(`Loaded ${(candidates.length + newItems.length).toLocaleString()} of ${res.total.toLocaleString()}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load more");
    } finally {
      setLoadingMore(false);
    }
  }, [loadingMore, hasMore, cursor, debouncedSearch, location, confidence, selectedDNA, openToWork, minScore, sortBy, sortDir, candidates.length]);

  // ── Table Virtualization ───────────────────────────────────────────────────
  const parentRef = useRef<HTMLDivElement>(null);

  const rowVirtualizer = useVirtualizer({
    count: candidates.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 53,
    overscan: 10,
  });

  const virtualRows = rowVirtualizer.getVirtualItems();
  const totalSize = rowVirtualizer.getTotalSize();

  const paddingTop = virtualRows.length > 0 ? virtualRows[0].start : 0;
  const paddingBottom = virtualRows.length > 0 ? totalSize - virtualRows[virtualRows.length - 1].end : 0;

  // Infinite Scroll Trigger
  useEffect(() => {
    if (virtualRows.length === 0) return;
    const lastVisibleIndex = virtualRows[virtualRows.length - 1].index;
    if (lastVisibleIndex >= candidates.length - 5) {
      loadNextCursor();
    }
  }, [virtualRows, candidates.length, loadNextCursor]);

  // ── Export Menu Setup ──────────────────────────────────────────────────────
  const exportMenuRef = useRef<HTMLDivElement>(null);
  const [exportMenuOpen, setExportMenuOpen] = useState(false);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (exportMenuRef.current && !exportMenuRef.current.contains(event.target as Node)) {
        setExportMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const triggerExport = (options: { limit?: number; type?: "current_view" | "current_filters" | "selected" | "all" }) => {
    setExportMenuOpen(false);

    const exportParams: any = {
      ...(debouncedSearch ? { search: debouncedSearch } : {}),
      ...(location !== "all" ? { location } : {}),
      ...(confidence !== "all" ? { confidence } : {}),
      ...(selectedDNA.size === 1 ? { career_dna: [...selectedDNA][0] } : {}),
      ...(openToWork ? { open_to_work: true } : {}),
      ...(minScore > 0 ? { min_score: minScore / 100 } : {}),
      sort_by: sortBy,
      sort_dir: sortDir,
    };

    if (options.limit) {
      exportParams.limit = options.limit;
    } else if (options.type === "current_view") {
      exportParams.limit = candidates.length;
    } else if (options.type === "selected") {
      exportParams.selected_ids = Array.from(selected).join(",");
    } else if (options.type === "all") {
      exportParams.export_all = true;
    }

    const exportURL = getExportURL(exportParams);
    const link = document.createElement("a");
    link.href = exportURL;
    link.setAttribute("download", "talentgraph-export.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // ── Log line animation ─────────────────────────────────────────────────────
  useEffect(() => {
    const interval = setInterval(() => {
      setLogLine((prev) =>
        prev.includes("Ranked")
          ? `Re-indexing vector space... ${Math.floor(Math.random() * 999)}ms`
          : prev
      );
    }, 4000);
    return () => clearInterval(interval);
  }, []);

  // ── Selection helpers ──────────────────────────────────────────────────────
  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else if (next.size < 2) next.add(id);
      return next;
    });
  };

  const toggleDNA = (dna: CareerDNA) => {
    setSelectedDNA((prev) => {
      const next = new Set(prev);
      if (next.has(dna)) next.delete(dna);
      else next.add(dna);
      return next;
    });
  };

  const handleCompare = () => {
    const ids = Array.from(selected);
    if (ids.length === 2) {
      router.push(`/compare?a=${encodeURIComponent(ids[0])}&b=${encodeURIComponent(ids[1])}`);
    }
  };

  const handleSort = (field: CandidateQueryParams["sort_by"]) => {
    if (sortBy === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(field);
      setSortDir("asc");
    }
  };

  const sparkDirection = (c: CandidateListItem): "up" | "flat" | "down" | "mixed" => {
    const traj = c.trajectory;
    if (!traj) return "flat";
    if (traj.direction >= 70) return "up";
    if (traj.direction <= 30) return "down";
    return "flat";
  };

  const SortIcon = ({ field }: { field: CandidateQueryParams["sort_by"] }) => {
    if (sortBy !== field) return <span className="ml-1 opacity-30">↕</span>;
    return <span className="ml-1 text-secondary">{sortDir === "asc" ? "↑" : "↓"}</span>;
  };

  // ── Render ─────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="mx-auto max-w-container px-margin-mobile py-8 md:px-margin-desktop pt-24">
        <LoadingSpinner label="Loading rankings..." />
        <div className="mt-8 space-y-3">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        </div>
      </div>
    );
  }

  if (error && candidates.length === 0) {
    return (
      <div className="mx-auto max-w-container px-margin-mobile py-8 md:px-margin-desktop pt-24">
        <ErrorState message={error} onRetry={loadFirstCursor} />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-container px-margin-mobile py-8 md:px-margin-desktop space-y-stack-md pt-24">
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-1">
          <p className="font-label-sm text-xs uppercase tracking-wider text-tertiary">Rankings</p>
          <h1 className="font-headline-lg text-headline-lg text-white">
            AI Engineer — {total.toLocaleString()} Candidates
          </h1>
        </div>
        <div className="flex gap-2">
          {/* Custom Dropdown Export Menu */}
          <div className="relative" ref={exportMenuRef}>
            <Button variant="outline" onClick={() => setExportMenuOpen(!exportMenuOpen)}>
              Export CSV
              <span className="material-symbols-outlined ml-1 text-sm">arrow_drop_down</span>
            </Button>
            {exportMenuOpen && (
              <div className="absolute right-0 mt-2 w-56 rounded border border-white/10 bg-surface-container-high/90 backdrop-blur-xl p-1.5 shadow-2xl z-50 animate-in fade-in slide-in-from-top-1 duration-150">
                <div className="px-2 py-1 text-[9px] font-label-sm uppercase tracking-wider text-secondary/70 border-b border-white/5 mb-1">
                  Export Custom Slice
                </div>
                <button onClick={() => triggerExport({ limit: 50 })} className="w-full text-left px-2 py-1.5 font-label-sm text-[11px] hover:bg-tertiary/10 rounded transition-colors text-on-surface hover:text-tertiary">Top 50 Candidates</button>
                <button onClick={() => triggerExport({ limit: 100 })} className="w-full text-left px-2 py-1.5 font-label-sm text-[11px] hover:bg-tertiary/10 rounded transition-colors text-on-surface hover:text-tertiary">Top 100 Candidates</button>
                <button onClick={() => triggerExport({ limit: 200 })} className="w-full text-left px-2 py-1.5 font-label-sm text-[11px] hover:bg-tertiary/10 rounded transition-colors text-on-surface hover:text-tertiary">Top 200 Candidates</button>
                <button onClick={() => triggerExport({ limit: 300 })} className="w-full text-left px-2 py-1.5 font-label-sm text-[11px] hover:bg-tertiary/10 rounded transition-colors text-on-surface hover:text-tertiary">Top 300 Candidates</button>
                <button onClick={() => triggerExport({ limit: 500 })} className="w-full text-left px-2 py-1.5 font-label-sm text-[11px] hover:bg-tertiary/10 rounded transition-colors text-on-surface hover:text-tertiary">Top 500 Candidates</button>
                <button onClick={() => triggerExport({ limit: 1000 })} className="w-full text-left px-2 py-1.5 font-label-sm text-[11px] hover:bg-tertiary/10 rounded transition-colors text-on-surface hover:text-tertiary">Top 1,000 Candidates</button>
                
                <div className="px-2 py-1 text-[9px] font-label-sm uppercase tracking-wider text-secondary/70 border-t border-b border-white/5 my-1 py-1">
                  Export Filtered View
                </div>
                <button onClick={() => triggerExport({ type: 'current_view' })} className="w-full text-left px-2 py-1.5 font-label-sm text-[11px] hover:bg-tertiary/10 rounded transition-colors text-on-surface hover:text-tertiary">Current Loaded View ({candidates.length})</button>
                <button onClick={() => triggerExport({ type: 'current_filters' })} className="w-full text-left px-2 py-1.5 font-label-sm text-[11px] hover:bg-tertiary/10 rounded transition-colors text-on-surface hover:text-tertiary">All Filtered Results</button>
                
                <div className="px-2 py-1 text-[9px] font-label-sm uppercase tracking-wider text-secondary/70 border-t border-b border-white/5 my-1 py-1">
                  Export Selections
                </div>
                <button 
                  onClick={() => triggerExport({ type: 'selected' })} 
                  disabled={selected.size === 0} 
                  className="w-full text-left px-2 py-1.5 font-label-sm text-[11px] hover:bg-tertiary/10 rounded transition-colors text-on-surface hover:text-tertiary disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-on-surface-variant"
                >
                  Selected Candidates ({selected.size})
                </button>
                <button onClick={() => triggerExport({ type: 'all' })} className="w-full text-left px-2 py-1.5 font-label-sm text-[11px] hover:bg-tertiary/10 rounded transition-colors border-t border-white/5 mt-1 pt-1.5 text-on-surface hover:text-tertiary">Export Entire Dataset (100K)</button>
              </div>
            )}
          </div>
          {selected.size === 2 && (
            <Button onClick={handleCompare}>Compare Selected</Button>
          )}
        </div>
      </div>

      <div className="flex flex-col gap-6 lg:flex-row">
        {/* ── Sidebar ── */}
        <aside className="w-full shrink-0 space-y-6 lg:w-72">
          {/* Engine status */}
          <div className="relative overflow-hidden rounded border border-white/5 bg-surface-container-low/40 p-4 glass-panel">
            <SignalField opacity={0.2} className="rounded" />
            <div className="relative z-10 space-y-1">
              <p className="font-label-sm text-[10px] uppercase tracking-wider text-tertiary">Engine Status</p>
              <p className="font-data-mono text-[11px] text-on-surface-variant leading-relaxed">{logLine}</p>
            </div>
          </div>

          {/* Filters */}
          <div className="rounded border border-white/5 bg-surface-container-low/40 p-4 space-y-4 glass-panel">
            <input
              type="text"
              placeholder="Search ID, title, or name..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded border border-white/5 bg-surface-container-low/60 etched-input px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-tertiary font-label-sm text-xs text-white"
            />

            <div className="space-y-1.5">
              <label className="text-[10px] font-label-sm uppercase tracking-wider text-secondary">
                Location
              </label>
              <Select value={location} onValueChange={setLocation}>
                <SelectTrigger className="mt-1">
                  <SelectValue placeholder="All locations" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All locations</SelectItem>
                  {locations.map((loc) => (
                    <SelectItem key={loc} value={loc}>{loc}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <label className="text-[10px] font-label-sm uppercase tracking-wider text-secondary">
                Confidence
              </label>
              <Select value={confidence} onValueChange={setConfidence}>
                <SelectTrigger className="mt-1">
                  <SelectValue placeholder="All" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All</SelectItem>
                  {ALL_CONFIDENCE.map((c) => (
                    <SelectItem key={c} value={c}>{c}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center justify-between text-sm">
              <span className="text-on-surface-variant font-body-md text-xs uppercase tracking-wider">Open to Work only</span>
              <Switch checked={openToWork} onCheckedChange={setOpenToWork} />
            </div>

            <div className="space-y-1.5">
              <label className="text-[10px] font-label-sm uppercase tracking-wider text-secondary">
                Min Score: {minScore}%
              </label>
              <input
                type="range"
                min={0}
                max={90}
                step={5}
                value={minScore}
                onChange={(e) => setMinScore(Number(e.target.value))}
                className="mt-2 w-full accent-tertiary"
              />
            </div>

            <div>
              <p className="mb-2 text-[10px] font-label-sm uppercase tracking-wider text-secondary">
                Career DNA
              </p>
              <div className="space-y-2">
                {ALL_DNA.map((dna) => (
                  <label key={dna} className="flex items-center gap-2 text-sm cursor-pointer text-on-surface-variant hover:text-white transition-colors">
                    <Checkbox
                      checked={selectedDNA.has(dna)}
                      onCheckedChange={() => toggleDNA(dna)}
                    />
                    <span className="truncate text-xs font-body-md">{dna}</span>
                  </label>
                ))}
              </div>
              {selectedDNA.size > 1 && (
                <p className="mt-2 font-label-sm text-[10px] text-on-surface-variant">
                  Multi-DNA filter active.
                </p>
              )}
            </div>

            {/* Sort controls */}
            <div className="space-y-2">
              <p className="text-[10px] font-label-sm uppercase tracking-wider text-secondary">
                Sort By
              </p>
              <div className="flex flex-wrap gap-1">
                {(["rank", "final_score", "capability", "trajectory", "notice_period"] as const).map((f) => (
                  <button
                    key={f}
                    onClick={() => handleSort(f)}
                    className={`rounded px-2.5 py-1 text-[11px] font-label-sm uppercase tracking-wider transition-all duration-200 ${
                      sortBy === f
                        ? "frozen-glow text-white border-tertiary/50"
                        : "bg-surface-container-low/40 text-on-surface-variant border border-white/5 hover:border-white/10 hover:text-white"
                    }`}
                  >
                    {f.replace("_", " ")}
                    {sortBy === f && (sortDir === "asc" ? " ↑" : " ↓")}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </aside>

        {/* ── Table ── */}
        <div className="min-w-0 flex-1">
          <div ref={parentRef} className="overflow-x-auto overflow-y-auto max-h-[600px] relative rounded border border-white/5 bg-surface-container-low/40 glass-panel shadow-2xl">
            <table className="w-full min-w-[900px] text-sm">
              <thead className="border-b border-white/5 bg-surface-container-low/80 backdrop-blur-md sticky top-0 z-20">
                <tr className="font-label-sm text-[10px] uppercase tracking-wider text-secondary">
                  <th className="p-3 w-10"></th>
                  <th
                    className="p-3 text-left cursor-pointer hover:text-tertiary transition-colors"
                    onClick={() => handleSort("rank")}
                  >
                    Rank <SortIcon field="rank" />
                  </th>
                  <th
                    className="p-3 text-left cursor-pointer hover:text-tertiary transition-colors"
                    onClick={() => handleSort("final_score")}
                  >
                    Score <SortIcon field="final_score" />
                  </th>
                  <th className="p-3 text-left">Confidence</th>
                  <th className="p-3 text-left">ID</th>
                  <th className="p-3 text-left">Title</th>
                  <th className="p-3 text-left">Career DNA</th>
                  <th className="p-3 text-left">Location</th>
                  <th
                    className="p-3 text-left cursor-pointer hover:text-tertiary transition-colors"
                    onClick={() => handleSort("notice_period")}
                  >
                    Notice <SortIcon field="notice_period" />
                  </th>
                  <th className="p-3 text-center">OTW</th>
                </tr>
              </thead>
              <tbody>
                {paddingTop > 0 && (
                  <tr>
                    <td colSpan={10} style={{ height: `${paddingTop}px` }} />
                  </tr>
                )}
                {virtualRows.map((virtualRow) => {
                  const c = candidates[virtualRow.index];
                  if (!c) return null;
                  return (
                    <tr
                      key={c.candidate_id}
                      className={`border-b border-white/5 transition-all duration-150 hover:bg-white/[0.02] hover-shimmer cursor-pointer ${
                        c.rank === 1 ? "border-l border-l-tertiary bg-tertiary/5" : ""
                      }`}
                      onClick={() => router.push(`/candidate/${encodeURIComponent(c.candidate_id)}`)}
                    >
                      <td className="p-3" onClick={(e) => e.stopPropagation()}>
                        <Checkbox
                          checked={selected.has(c.candidate_id)}
                          onCheckedChange={() => toggleSelect(c.candidate_id)}
                          disabled={!selected.has(c.candidate_id) && selected.size >= 2}
                        />
                      </td>
                      <td className="p-3 font-data-mono font-medium text-xs text-white/80">#{c.rank}</td>
                      <td className="p-3">
                        <div className="flex items-center gap-2">
                          <ScorePill score={c.final_score} />
                          <TrajectorySparkline direction={sparkDirection(c)} />
                        </div>
                      </td>
                      <td className="p-3">
                        <ConfidenceBadge confidence={c.confidence.label} />
                      </td>
                      <td className="p-3 font-data-mono text-xs">
                        <Link
                          href={`/candidate/${encodeURIComponent(c.candidate_id)}`}
                          className="text-tertiary hover:underline hover:text-white transition-colors"
                          onClick={(e) => e.stopPropagation()}
                        >
                          {c.candidate_id}
                        </Link>
                      </td>
                      <td className="p-3 text-white/90 font-body-md font-medium text-xs">{c.title}</td>
                      <td className="p-3">
                        <CareerDNABadge dna={c.career_dna} />
                      </td>
                      <td className="p-3 text-on-surface-variant text-xs">{getCity(c.location)}</td>
                      <td className="p-3 font-data-mono text-xs">
                        {c.notice_period_days != null ? `${c.notice_period_days}d` : "—"}
                      </td>
                      <td className="p-3 text-center">
                        <span
                          className="material-symbols-outlined text-base"
                          style={{ color: c.open_to_work ? "#7dd3fc" : "#475569" }}
                        >
                          {c.open_to_work ? "check_circle" : "cancel"}
                        </span>
                      </td>
                    </tr>
                  );
                })}
                {paddingBottom > 0 && (
                  <tr>
                    <td colSpan={10} style={{ height: `${paddingBottom}px` }} />
                  </tr>
                )}
              </tbody>
            </table>

            {candidates.length === 0 && !loading && (
              <p className="p-8 text-center font-label-sm text-xs text-on-surface-variant">
                No candidates match your filters.
              </p>
            )}
          </div>

          {/* Load more indicator */}
          {loadingMore && (
            <div className="mt-4 flex justify-center items-center gap-3">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-tertiary border-t-transparent" />
              <span className="font-label-sm text-xs text-on-surface-variant">
                Loading more candidates...
              </span>
            </div>
          )}

          {/* End of results indicator / summary */}
          {!loadingMore && candidates.length > 0 && (
            <div className="mt-4 text-center font-label-sm text-xs text-on-surface-variant space-y-1">
              <p>
                Showing {candidates.length.toLocaleString()} of {total.toLocaleString()} candidates
              </p>
              {!hasMore && (
                <p className="text-tertiary font-medium">
                  ✓ All candidates loaded (End of Results)
                </p>
              )}
            </div>
          )}

          {/* Non-critical error (mid-pagination) */}
          {error && candidates.length > 0 && (
            <p className="mt-3 text-center font-label-sm text-xs text-error">
              {error}{" "}
              <button onClick={loadFirstCursor} className="underline hover:text-white transition-colors ml-1">
                Retry
              </button>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
