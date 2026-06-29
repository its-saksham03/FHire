/**
 * api.ts — FHire API client
 *
 * All data fetching goes through this module.
 * Zero mock data. Every function calls the FastAPI backend.
 *
 * Base URL: NEXT_PUBLIC_API_URL (default http://localhost:8000)
 * Timeout:  NEXT_PUBLIC_API_TIMEOUT_MS (default 30000ms)
 */

import axios, { AxiosError } from "axios";
import type {
  CandidateDetail,
  CandidateQueryParams,
  CompareResult,
  HealthResponse,
  PaginatedCandidates,
  Stats,
  RankResponse,
} from "./types";
import type { RequirementSummary } from "./jd-parser";

// ─── CONFIG ──────────────────────────────────────────────────────────────────

const BASE_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
const TIMEOUT_MS = Number(process.env.NEXT_PUBLIC_API_TIMEOUT_MS ?? 30000);
const DEFAULT_PAGE_SIZE = Number(process.env.NEXT_PUBLIC_PAGE_SIZE ?? 50);

// ─── AXIOS INSTANCE ──────────────────────────────────────────────────────────

const http = axios.create({
  baseURL: `${BASE_URL}/api`,
  timeout: TIMEOUT_MS,
  headers: { "Content-Type": "application/json" },
});

// ─── ERROR CLASS ─────────────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(
    message: string,
    public status?: number,
    public detail?: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function normalizeError(err: unknown): ApiError {
  if (err instanceof ApiError) return err;

  if (axios.isAxiosError(err)) {
    const axErr = err as AxiosError<{ detail?: string }>;
    const status = axErr.response?.status;
    const detail =
      axErr.response?.data?.detail ??
      axErr.response?.statusText ??
      axErr.message;

    if (!axErr.response) {
      // Network error / timeout / CORS
      if (axErr.code === "ECONNABORTED" || axErr.message.includes("timeout")) {
        return new ApiError(
          "Request timed out. The backend may be processing a large dataset — please retry.",
          408,
          detail
        );
      }
      return new ApiError(
        "Cannot connect to backend. Ensure the FastAPI server is running on " + BASE_URL,
        0,
        detail
      );
    }

    if (status === 404) return new ApiError("Not found: " + detail, 404, detail);
    if (status === 503) return new ApiError("Backend unavailable: " + detail, 503, detail);
    return new ApiError(`Backend error (${status}): ${detail}`, status, detail);
  }

  if (err instanceof Error) return new ApiError(err.message);
  return new ApiError("An unexpected error occurred");
}

// ─── ENDPOINTS ───────────────────────────────────────────────────────────────

/**
 * GET /api/health
 * Confirm the backend is up and the ranked pool is ready.
 */
export async function getHealth(): Promise<HealthResponse> {
  try {
    const { data } = await http.get<HealthResponse>("/health");
    return data;
  } catch (err) {
    throw normalizeError(err);
  }
}

/**
 * GET /api/candidates
 * Paginated, searchable, filterable candidate list.
 * Never fetches the entire dataset — server-side pagination.
 */
export async function getCandidates(
  params: CandidateQueryParams = {},
  signal?: AbortSignal
): Promise<PaginatedCandidates> {
  try {
    const { data } = await http.get<PaginatedCandidates>("/candidates", {
      signal,
      params: {
        ...(params.cursor ? { cursor: params.cursor } : {}),
        limit: params.limit ?? params.page_size ?? DEFAULT_PAGE_SIZE,
        ...(params.page ? { page: params.page } : {}),
        ...(params.page_size ? { page_size: params.page_size } : {}),
        ...(params.search ? { search: params.search } : {}),
        ...(params.location ? { location: params.location } : {}),
        ...(params.confidence ? { confidence: params.confidence } : {}),
        ...(params.career_dna ? { career_dna: params.career_dna } : {}),
        ...(params.open_to_work ? { open_to_work: true } : {}),
        ...(params.min_score != null && params.min_score > 0
          ? { min_score: params.min_score }
          : {}),
        sort_by: params.sort_by ?? "rank",
        sort_dir: params.sort_dir ?? "asc",
      },
    });
    return data;
  } catch (err) {
    throw normalizeError(err);
  }
}

/**
 * Construct the full URL for exporting candidates as a CSV.
 */
export function getExportURL(
  params: CandidateQueryParams & { limit?: number; selected_ids?: string; export_all?: boolean } = {}
): string {
  const query: Record<string, string> = {
    sort_by: params.sort_by ?? "rank",
    sort_dir: params.sort_dir ?? "asc",
  };
  
  if (params.search) query.search = params.search;
  if (params.location) query.location = params.location;
  if (params.confidence) query.confidence = params.confidence;
  if (params.career_dna) query.career_dna = params.career_dna;
  if (params.open_to_work) query.open_to_work = "true";
  if (params.min_score != null && params.min_score > 0) query.min_score = String(params.min_score);
  
  if (params.limit != null) query.limit = String(params.limit);
  if (params.selected_ids) query.selected_ids = params.selected_ids;
  if (params.export_all) query.export_all = "true";

  const searchParams = new URLSearchParams(query);
  return `${BASE_URL}/api/candidates/export?${searchParams.toString()}`;
}

/**
 * GET /api/candidates/locations
 * Distinct city list for filter dropdowns.
 */
export async function getLocations(): Promise<string[]> {
  try {
    const { data } = await http.get<{ locations: string[] }>("/candidates/locations");
    return data.locations;
  } catch (err) {
    throw normalizeError(err);
  }
}

/**
 * GET /api/candidate/{id}
 * Full detail for a single candidate including profile, signals, and counterfactual.
 */
export async function getCandidateDetail(id: string, fromSource?: string, context?: string): Promise<CandidateDetail> {
  try {
    const params: Record<string, string> = {};
    if (fromSource) params.from_source = fromSource;
    if (context) params.context = context;
    const { data } = await http.get<CandidateDetail>(`/candidate/${encodeURIComponent(id)}`, { params });
    return data;
  } catch (err) {
    throw normalizeError(err);
  }
}

/**
 * POST /api/compare
 * Head-to-head comparison of two candidates by ID.
 */
export async function compareCandidates(idA: string, idB: string): Promise<CompareResult> {
  try {
    const { data } = await http.post<CompareResult>("/compare", {
      candidate_a_id: idA,
      candidate_b_id: idB,
    });
    return data;
  } catch (err) {
    throw normalizeError(err);
  }
}

/**
 * GET /api/stats
 * Aggregate analytics for the dashboard.
 */
export async function getStats(): Promise<Stats> {
  try {
    const { data } = await http.get<Stats>("/stats");
    return data;
  } catch (err) {
    throw normalizeError(err);
  }
}

/**
 * POST /api/rank (empty body = auto-load from file)
 * Triggers a full re-rank of the candidate pool.
 * Called by the Demo page to refresh rankings.
 */
export async function triggerRank(): Promise<{ total_scored: number; total_disqualified: number }> {
  try {
    const { data } = await http.post<{ total_scored: number; total_disqualified: number }>(
      "/rank",
      {},
      { timeout: 120_000 } // re-ranking 100k candidates takes time
    );
    return data;
  } catch (err) {
    throw normalizeError(err);
  }
}

// ─── CSV EXPORT (client-side, from paginated data) ───────────────────────────

export function candidatesToCSV(candidates: PaginatedCandidates["results"]): string {
  const headers = [
    "Rank",
    "Candidate ID",
    "Final Score",
    "Confidence",
    "Title",
    "Company",
    "Location",
    "Career DNA",
    "Capability",
    "Trajectory",
    "Recruitability",
    "Authenticity",
    "Notice Period (days)",
    "Open to Work",
    "Reasoning",
  ];

  const escape = (v: string | number | boolean | null | undefined) => {
    const s = String(v ?? "");
    if (s.includes(",") || s.includes('"') || s.includes("\n")) {
      return `"${s.replace(/"/g, '""')}"`;
    }
    return s;
  };

  const rows = candidates.map((c) =>
    [
      c.rank,
      c.candidate_id,
      c.final_score.toFixed(3),
      c.confidence.label,
      c.title,
      c.company,
      c.location,
      c.career_dna,
      c.capability.toFixed(1),
      (c.trajectory?.score ?? 0).toFixed(1),
      (c.recruitability?.score ?? 0).toFixed(1),
      (c.authenticity?.score ?? 0).toFixed(1),
      c.notice_period_days ?? "",
      c.open_to_work,
      c.reasoning,
    ]
      .map(escape)
      .join(",")
  );

  return [headers.join(","), ...rows].join("\n");
}

export function downloadCSV(
  candidates: PaginatedCandidates["results"],
  filename = "talentgraph-rankings.csv"
) {
  const csv = candidatesToCSV(candidates);
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

/**
 * POST /api/rank
 * Score and rank candidates using live custom weights.
 */
export async function rankCandidates(
  weights: {
    capability: number;
    trajectory: number;
    recruitability: number;
    authenticity: number;
  },
  topN: number = 10,
  requirements: RequirementSummary | null = null
): Promise<RankResponse> {
  try {
    const { data } = await http.post<RankResponse>(
      "/rank",
      {
        weights,
        top_n: topN,
        requirements,
      },
      { timeout: 120_000 }
    );
    return data;
  } catch (err) {
    throw normalizeError(err);
  }
}

