"""
backend/api/schemas.py — FHire Pydantic Request & Response Models

All FastAPI endpoints declare their I/O using these models.
Member 3 (frontend) should read these alongside API_DOCUMENTATION.md.

Naming convention:
    *Request  — inbound body
    *Response — outbound body
    *Item     — reusable nested model
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


# ─── SHARED NESTED MODELS ─────────────────────────────────────────────────────

class RecruitabilityBreakdown(BaseModel):
    """Sub-scores that make up the recruitability score."""
    availability: float = Field(..., description="Availability sub-score (0-40)")
    responsiveness: float = Field(..., description="Responsiveness sub-score (0-35)")
    logistics: float = Field(..., description="Logistics sub-score (0-25)")


class RecruitabilityItem(BaseModel):
    """Full recruitability result."""
    score: float = Field(..., description="Raw recruitability score (0-100)")
    multiplier: float = Field(..., description="Final-score multiplier (0.1-1.0)")
    breakdown: RecruitabilityBreakdown


class TrajectoryItem(BaseModel):
    """Full trajectory result from trajectory_engine."""
    score: float = Field(..., description="Trajectory score (0-100)")
    dna: str = Field(..., description="Career DNA label e.g. 'Startup Builder'")
    direction: float = Field(..., description="Direction sub-score (0-100)")
    velocity: float = Field(..., description="Velocity sub-score (0-100)")
    tenure: float = Field(..., description="Tenure stability sub-score (0-100)")
    tenure_avg_months: float = Field(..., description="Average months per role")
    is_job_hopper: bool = Field(..., description="True if avg tenure < 18 months")
    dna_multiplier: float = Field(..., description="DNA penalty/bonus multiplier")


class AuthenticityItem(BaseModel):
    """Full authenticity result."""
    score: float = Field(..., description="Authenticity score (0-100)")
    flags: list[str] = Field(default_factory=list, description="Detected issues e.g. skill inflation")


class ConfidenceItem(BaseModel):
    """System confidence in this candidate's ranking."""
    score: int = Field(..., description="Confidence score (0-100)")
    label: str = Field(..., description="'High' | 'Medium' | 'Low'")
    explanation: Optional[str] = Field(None, description="Human-readable rationale")


class CounterfactualImprovement(BaseModel):
    """A single hypothetical improvement scenario."""
    change: str = Field(..., description="Description of the change")
    rank_improvement: int = Field(..., description="Estimated ranks gained (positive = up)")
    score_delta: float = Field(..., description="Change in final score")
    feasibility: str = Field(..., description="How actionable this change is")


class CounterfactualItem(BaseModel):
    """Counterfactual output: 'what would it take to rank higher?'"""
    current_rank: int
    current_score: float
    top_improvements: list[CounterfactualImprovement] = Field(default_factory=list)
    summary: str


class RequirementMatchDetails(BaseModel):
    """Deterministic requirement match results and explainability."""
    score: float = Field(..., description="Requirement match score 0-100")
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    experience_matched: bool = Field(..., description="Experience criteria met")
    location_matched: bool = Field(..., description="Location criteria met")


class RankedCandidateItem(BaseModel):
    """A single ranked candidate as returned by /rank and /stats."""
    candidate_id: str
    rank: int
    final_score: float = Field(..., description="Final score in 0-1 range")
    capability: float = Field(..., description="Capability score 0-100")
    trajectory: dict[str, Any] = Field(..., description="Trajectory score dict")
    recruitability: dict[str, Any] = Field(..., description="Recruitability score dict")
    authenticity: dict[str, Any] = Field(..., description="Authenticity score dict")
    confidence: dict[str, Any] = Field(..., description="Confidence score dict")
    reasoning: str = Field(..., description="Grounded recruiter-style reasoning")
    counterfactual: Optional[dict[str, Any]] = Field(
        None, description="What-would-it-take output (may be None if not computed)"
    )
    career_dna: str = Field(..., description="Career DNA label extracted from trajectory")
    requirement_match: Optional[RequirementMatchDetails] = Field(
        None, description="Requirement matching score details"
    )
    years_of_experience: float = Field(0.0, description="Years of experience from profile")
    location: str = Field("Not specified", description="Location from profile")
    preferred_work_mode: Optional[str] = Field(None, description="Preferred work mode")


class DimensionComparison(BaseModel):
    """Per-dimension comparison between two candidates."""
    dimension: str
    score_a: float
    score_b: float
    difference: float
    advantage: str  # "clear advantage" | "slight advantage" | "roughly equal" | etc.
    winner: str     # "A" | "B" | "tie"


class CandidateMeta(BaseModel):
    """Display metadata for a candidate (used in compare response)."""
    candidate_id: str
    current_title: str
    location: str
    years_of_experience: float
    career_dna: str
    notice_period: Optional[int] = None
    open_to_work: bool
    confidence_label: str


# ─── DNA / DISTRIBUTION ITEMS ─────────────────────────────────────────────────

class DNADistribution(BaseModel):
    """Count of candidates per Career DNA category."""
    Startup_Builder: int = Field(0, alias="Startup Builder")
    Scale_Expert: int = Field(0, alias="Scale Expert")
    Product_Engineer: int = Field(0, alias="Product Engineer")
    Research_Specialist: int = Field(0, alias="Research Specialist")
    Consulting_Only: int = Field(0, alias="Consulting Only")
    Unclear: int = 0

    class Config:
        populate_by_name = True


class ConfidenceDistribution(BaseModel):
    """Count of candidates per confidence label."""
    High: int = 0
    Medium: int = 0
    Low: int = 0


# ─── REQUEST MODELS ───────────────────────────────────────────────────────────

class RankRequest(BaseModel):
    """
    POST /api/rank — request body.

    **Swagger / quick-test usage:** omit `candidates` entirely (or pass an
    empty list `[]`). The backend will automatically load every candidate
    from `data/candidates.jsonl` using the embeddings and distributions
    already in memory from startup.

    **Normal usage:** supply up to 100 raw candidate dicts in the same
    structure as `candidates.jsonl`. The backend uses pre-loaded embeddings
    and distributions; semantic scores are derived from the pre-computed
    embeddings.
    """
class RequirementSummaryRequest(BaseModel):
    """Job description requirements summary parsed from the frontend."""
    role: str = Field("", description="Detected job title/role")
    skills: list[str] = Field(default_factory=list, description="Required technical skills")
    experience: str = Field("", description="Experience range requested")
    location: str = Field("", description="Job location")
    remoteHybrid: str = Field("", description="Work arrangement format")
    employmentType: str = Field("", description="Nature of employment")
    keywords: list[str] = Field(default_factory=list, description="Non-skill hiring keywords")


class RankRequest(BaseModel):
    """
    POST /api/rank — request body.

    **Swagger / quick-test usage:** omit `candidates` entirely (or pass an
    empty list `[]`). The backend will automatically load every candidate
    from `data/candidates.jsonl` using the embeddings and distributions
    already in memory from startup.

    **Normal usage:** supply up to 100 raw candidate dicts in the same
    structure as `candidates.jsonl`. The backend uses pre-loaded embeddings
    and distributions; semantic scores are derived from the pre-computed
    embeddings.
    """
    candidates: Optional[list[dict[str, Any]]] = Field(
        None,
        description=(
            "List of raw candidate dicts (candidates.jsonl format). "
            "Leave empty or omit to automatically load data/candidates.jsonl."
        ),
    )
    include_counterfactual: bool = Field(
        False,
        description="Set True to include counterfactual output (slower)",
    )
    top_n: Optional[int] = Field(
        None,
        description="Optional maximum number of ranked results to return in response",
    )
    weights: Optional[dict[str, float]] = Field(
        None,
        description="Dynamic dimension weights to apply",
    )
    requirements: Optional[RequirementSummaryRequest] = Field(
        None,
        description="Extracted JD hiring requirements",
    )


class CompareRequest(BaseModel):
    """
    POST /api/compare — request body.

    Supply either two candidate IDs (looked up from the in-memory ranked pool)
    or two full score dicts. If IDs are supplied, the backend looks them up
    from the last ranked batch held in memory.
    """
    candidate_a_id: Optional[str] = Field(None, description="ID of Candidate A")
    candidate_b_id: Optional[str] = Field(None, description="ID of Candidate B")
    scores_a: Optional[dict[str, Any]] = Field(
        None, description="Full score dict for Candidate A (alternative to ID)"
    )
    scores_b: Optional[dict[str, Any]] = Field(
        None, description="Full score dict for Candidate B (alternative to ID)"
    )


# ─── RESPONSE MODELS ──────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    """GET /api/health response."""
    status: str = "ok"
    version: str = "4.0"
    embeddings_loaded: bool
    distributions_loaded: bool
    ranked_pool_size: int = Field(
        0, description="Number of candidates currently held in the ranked pool"
    )


class RankResponse(BaseModel):
    """POST /api/rank response."""
    total_scored: int
    total_disqualified: int
    results: list[RankedCandidateItem]


class CandidateDetailResponse(BaseModel):
    """GET /api/candidate/{candidate_id} response."""
    candidate_id: str
    rank: Optional[int] = None
    final_score: float
    capability: float
    trajectory: dict[str, Any]
    recruitability: dict[str, Any]
    authenticity: dict[str, Any]
    confidence: dict[str, Any]
    reasoning: str
    counterfactual: Optional[dict[str, Any]] = None
    career_dna: str
    profile: dict[str, Any] = Field(
        default_factory=dict, description="Raw profile fields for display"
    )
    signals: dict[str, Any] = Field(
        default_factory=dict, description="Raw redrob_signals for display"
    )
    requirement_match: Optional[RequirementMatchDetails] = Field(
        None, description="Requirement matching details if loaded from recruiter intake workspace context"
    )


class CompareResponse(BaseModel):
    """POST /api/compare response."""
    candidate_a: CandidateMeta
    candidate_b: CandidateMeta
    final_score_a: float
    final_score_b: float
    final_score_diff: float
    dimension_comparisons: list[DimensionComparison]
    dimensions_a_wins: list[str]
    dimensions_b_wins: list[str]
    verdict: str
    reasoning_a: str
    reasoning_b: str


class StatsResponse(BaseModel):
    """GET /api/stats response — aggregate insights for the analytics dashboard."""
    total_ranked: int
    disqualified_count: int

    avg_capability: float
    avg_trajectory: float
    avg_recruitability: float
    avg_authenticity: float
    avg_notice_period_days: float
    open_to_work_count: int

    dna_distribution: dict[str, int] = Field(
        default_factory=dict,
        description="Count per Career DNA category",
    )
    confidence_distribution: dict[str, int] = Field(
        default_factory=dict,
        description="Count per confidence label: High / Medium / Low",
    )
    score_buckets: dict[str, int] = Field(
        default_factory=dict,
        description="Histogram of final scores: '0.0-0.2', '0.2-0.4', etc.",
    )
    location_distribution: list[dict] = Field(
        default_factory=list,
        description="Top cities: [{city, count}]",
    )
    notice_period_distribution: list[dict] = Field(
        default_factory=list,
        description="Notice period buckets: [{range, count}]",
    )
