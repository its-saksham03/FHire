// ─── SHARED PRIMITIVES ─────────────────────────────────────────────────────

export type Confidence = "High" | "Medium" | "Low";

export type CareerDNA =
  | "Startup Builder"
  | "Scale Expert"
  | "Product Engineer"
  | "Research Specialist"
  | "Consulting Only"
  | "Unclear";

export type Proficiency = "beginner" | "intermediate" | "advanced" | "expert";

// ─── BACKEND SCORE DICTS ────────────────────────────────────────────────────

export interface TrajectoryScore {
  score: number;
  dna: CareerDNA;
  direction: number;
  velocity: number;
  tenure: number;
  tenure_avg_months: number;
  is_job_hopper: boolean;
  dna_multiplier: number;
}

export interface RecruitabilityScore {
  score: number;
  multiplier: number;
  breakdown: {
    availability: number;
    responsiveness: number;
    logistics: number;
  };
}

export interface AuthenticityScore {
  score: number;
  flags: string[];
}

export interface ConfidenceScore {
  score: number;
  label: Confidence;
  explanation?: string;
}

// ─── CANDIDATE LIST ITEM (from GET /api/candidates) ───────────────────────

export interface CareerTimelineEntry {
  company: string;
  title: string;
  duration_months: number;
  start_date: string;
  end_date: string | null;
  is_current: boolean;
}

export interface SkillEntry {
  name: string;
  proficiency: Proficiency;
  endorsements: number;
  duration_months: number;
  trust_score: number | null;
}

export interface CandidateListItem {
  candidate_id: string;
  rank: number;
  final_score: number;
  capability: number;
  trajectory: TrajectoryScore;
  recruitability: RecruitabilityScore;
  authenticity: AuthenticityScore;
  confidence: ConfidenceScore;
  reasoning: string;
  career_dna: CareerDNA;
  title: string;
  company: string;
  location: string;
  years_of_experience: number;
  notice_period_days: number | null;
  open_to_work: boolean;
  response_rate: number;
  github_score: number | null;
  career_timeline: CareerTimelineEntry[];
  skills: SkillEntry[];
}

// ─── PAGINATED RESPONSE ─────────────────────────────────────────────────────

export interface PaginatedCandidates {
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  results: CandidateListItem[];
  items?: CandidateListItem[];
  next_cursor?: string | null;
  has_more?: boolean;
}

// ─── CANDIDATE DETAIL (from GET /api/candidate/{id}) ───────────────────────

export interface CandidateDetail {
  candidate_id: string;
  rank: number | null;
  final_score: number;
  capability: number;
  trajectory: TrajectoryScore;
  recruitability: RecruitabilityScore;
  authenticity: AuthenticityScore;
  confidence: ConfidenceScore;
  reasoning: string;
  counterfactual: CounterfactualDetail | null;
  career_dna: CareerDNA;
  profile: RawProfile;
  signals: RawSignals;
  requirement_match?: {
    score: number;
    matched_skills: string[];
    missing_skills: string[];
    experience_matched: boolean;
    location_matched: boolean;
  };
}

export interface CounterfactualImprovement {
  change: string;
  rank_improvement: number;
  score_delta: number;
  feasibility: string;
}

export interface CounterfactualDetail {
  current_rank: number;
  current_score: number;
  top_improvements: CounterfactualImprovement[];
  summary: string;
}

// ─── RAW PROFILE / SIGNALS (nested in CandidateDetail) ─────────────────────

export interface RawProfile {
  anonymized_name: string;
  headline: string;
  summary: string;
  location: string;
  country: string;
  years_of_experience: number;
  current_title: string;
  current_company: string;
  current_company_size: string;
  current_industry: string;
}

export interface RawSignals {
  profile_completeness_score: number;
  open_to_work_flag: boolean;
  notice_period_days: number;
  recruiter_response_rate: number;
  github_activity_score: number;
  verified_email: boolean;
  verified_phone: boolean;
  skill_assessment_scores?: Record<string, number>;
  last_active_date?: string;
  connection_count?: number;
}

// ─── COMPARE RESULT (from POST /api/compare) ────────────────────────────────

export interface CandidateMeta {
  candidate_id: string;
  current_title: string;
  location: string;
  years_of_experience: number;
  career_dna: CareerDNA;
  notice_period: number | null;
  open_to_work: boolean;
  confidence_label: Confidence;
}

export interface DimensionComparison {
  dimension: string;
  score_a: number;
  score_b: number;
  difference: number;
  advantage: string;
  winner: "A" | "B" | "tie";
}

export interface CompareResult {
  candidate_a: CandidateMeta;
  candidate_b: CandidateMeta;
  final_score_a: number;
  final_score_b: number;
  final_score_diff: number;
  dimension_comparisons: DimensionComparison[];
  dimensions_a_wins: string[];
  dimensions_b_wins: string[];
  verdict: string;
  reasoning_a: string;
  reasoning_b: string;
}

// ─── STATS (from GET /api/stats) ────────────────────────────────────────────

export interface Stats {
  total_ranked: number;
  disqualified_count: number;
  avg_capability: number;
  avg_trajectory: number;
  avg_recruitability: number;
  avg_authenticity: number;
  avg_notice_period_days: number;
  open_to_work_count: number;
  dna_distribution: Record<string, number>;
  confidence_distribution: Record<string, number>;
  score_buckets: Record<string, number>;
  location_distribution: Array<{ city: string; count: number }>;
  notice_period_distribution: Array<{ range: string; count: number }>;
}

// ─── HEALTH ─────────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: string;
  version: string;
  embeddings_loaded: boolean;
  distributions_loaded: boolean;
  ranked_pool_size: number;
}

// ─── QUERY PARAMS ───────────────────────────────────────────────────────────

export interface CandidateQueryParams {
  page?: number;
  page_size?: number;
  limit?: number;
  cursor?: string | null;
  search?: string;
  location?: string;
  confidence?: string;
  career_dna?: string;
  open_to_work?: boolean;
  min_score?: number;
  sort_by?: "rank" | "final_score" | "capability" | "trajectory" | "recruitability" | "authenticity" | "notice_period";
  sort_dir?: "asc" | "desc";
}

export interface RequirementMatchDetails {
  score: number;
  matched_skills: string[];
  missing_skills: string[];
  experience_matched: boolean;
  location_matched: boolean;
}

export interface RankedCandidateItem {
  candidate_id: string;
  rank: number;
  final_score: number;
  capability: number;
  trajectory: TrajectoryScore;
  recruitability: RecruitabilityScore;
  authenticity: AuthenticityScore;
  confidence: ConfidenceScore;
  reasoning: string;
  counterfactual?: CounterfactualDetail | null;
  career_dna: CareerDNA;
  requirement_match?: RequirementMatchDetails | null;
  years_of_experience: number;
  location: string;
  preferred_work_mode?: string | null;
}

export interface RankResponse {
  total_scored: number;
  total_disqualified: number;
  results: RankedCandidateItem[];
}

