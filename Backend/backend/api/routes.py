"""
backend/api/routes.py — FHire FastAPI Route Handlers

Every endpoint delegates all scoring to core/pipeline.py and core/comparator.py.
No scoring logic lives here. This file only:
    - Validates requests (via Pydantic schemas)
    - Calls the correct pipeline function
    - Shapes the response
    - Handles errors gracefully

Endpoints:
    GET  /api/health
    POST /api/rank
    GET  /api/candidate/{candidate_id}
    POST /api/compare
    GET  /api/stats
"""

from __future__ import annotations

import base64
import csv
import io
import json
import logging
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

import numpy as np
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

logger = logging.getLogger("talentgraph")

# Default path for the auto-load fallback (matches main.py default)
_CANDIDATES_JSONL = Path("data/candidates.jsonl")

from backend.api.schemas import (
    CandidateDetailResponse,
    CompareRequest,
    CompareResponse,
    DimensionComparison,
    CandidateMeta,
    HealthResponse,
    RankRequest,
    RankResponse,
    RankedCandidateItem,
    StatsResponse,
)
from core.comparator import compare_candidates
from core.pipeline import score_batch

router = APIRouter()


# ─── MODULE-LEVEL STATE ───────────────────────────────────────────────────────
# The backend loads embeddings and distributions ONCE at startup (see main.py).
# Routes access them through this shared state dict — no global variables, no
# re-loading per request.
#
# Keys set by main.py startup:
#   "jd_emb"              numpy array (embed_dim,)
#   "cand_embs_map"       dict candidate_id → embedding vector
#   "signal_distributions" dict from distributions.json
#   "ranked_pool"         list[dict] — last ranked result, keyed by candidate_id
#   "disqualified_count"  int — from last /rank call
#
# Access via the `app_state` dict injected at startup.
_state: dict[str, Any] = {
    "jd_emb": None,
    "cand_embs_map": {},
    "signal_distributions": {},
    "ranked_pool": [],          # list of score dicts from last /rank call
    "ranked_pool_index": {},    # candidate_id → score dict (for O(1) lookup)
    "disqualified_count": 0,
}


def get_state() -> dict[str, Any]:
    """Return the shared backend state. Called by main.py to inject loaded data."""
    return _state


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _extract_dna(score_dict: dict) -> str:
    """Pull career DNA from a score dict safely."""
    traj = score_dict.get("trajectory", {})
    if isinstance(traj, dict):
        return traj.get("dna", "Unclear")
    return "Unclear"


def _to_ranked_item(r: dict) -> RankedCandidateItem:
    """Convert a pipeline score dict to a RankedCandidateItem response model."""
    cand = r.get("candidate") or {}
    prof = cand.get("profile") or {}
    signals = cand.get("redrob_signals") or {}
    return RankedCandidateItem(
        candidate_id=r.get("candidate_id", ""),
        rank=r.get("rank", 0),
        final_score=r.get("final_score", 0.0),
        capability=r.get("capability", 0.0),
        trajectory=r.get("trajectory", {}),
        recruitability=r.get("recruitability", {}),
        authenticity=r.get("authenticity", {}),
        confidence=r.get("confidence", {}),
        reasoning=r.get("reasoning", ""),
        counterfactual=r.get("counterfactual"),
        career_dna=_extract_dna(r),
        requirement_match=r.get("requirement_match"),
        years_of_experience=float(prof.get("years_of_experience", 0.0)),
        location=prof.get("location", "Not specified"),
        preferred_work_mode=signals.get("preferred_work_mode"),
    )


def _calculate_requirement_match(c: dict, parsed_reqs: dict | None) -> dict:
    """Calculate deterministic requirement match metrics and details using precomputed lookup fields."""
    if not parsed_reqs:
        return {
            "score": 100.0,
            "matched_skills": [],
            "missing_skills": [],
            "experience_matched": True,
            "location_matched": True,
        }

    role_score = 100.0
    skills_score = 100.0
    experience_score = 100.0
    location_score = 100.0
    keyword_score = 100.0

    matched_skills = []
    missing_skills = []
    experience_matched = True
    location_matched = True

    # 1. Role Match (30%)
    role_lower = parsed_reqs["role_lower"]
    if role_lower and role_lower != "not specified":
        role_score = 0.0
        curr_title = c.get("current_title_lower", "")
        if role_lower in curr_title or curr_title in role_lower:
            role_score = 100.0
        else:
            req_words = parsed_reqs["role_words"]
            if req_words:
                match_count = 0
                for w in req_words:
                    if w in curr_title:
                        match_count += 1
                
                hist_titles = c.get("search_titles", [])
                for w in req_words:
                    for ht in hist_titles:
                        if w in ht:
                            match_count += 1
                            break

                match_ratio = match_count / len(req_words)
                role_score = min(100.0, match_ratio * 100.0)
                for w in req_words:
                    if w in curr_title:
                        role_score = max(role_score, 70.0)
            else:
                if role_lower in curr_title:
                    role_score = 100.0

    # 2. Skill Match (45%)
    req_skills = parsed_reqs["skills_lower"]
    if req_skills:
        cand_skills = c.get("search_skills", [])
        cand_skills_set = set(cand_skills)
        matched_req = []
        
        for rs in req_skills:
            if rs in cand_skills_set:
                matched_req.append(rs)
            else:
                found = False
                for cs in cand_skills:
                    if rs in cs or cs in rs:
                        found = True
                        break
                if found:
                    matched_req.append(rs)
                    
        orig_skills = parsed_reqs.get("orig_skills") or req_skills
        for idx, rs in enumerate(req_skills):
            orig_name = orig_skills[idx] if idx < len(orig_skills) else rs
            if rs in matched_req:
                matched_skills.append(orig_name)
            else:
                missing_skills.append(orig_name)
        skills_score = (len(matched_req) / len(req_skills)) * 100.0
    else:
        skills_score = 100.0

    # 3. Experience Match (15%)
    cand_exp = c.get("total_experience", 0.0)
    min_exp = parsed_reqs["min_exp"]
    max_exp = parsed_reqs["max_exp"]
    if min_exp > 0.0 or max_exp is not None:
        if cand_exp >= min_exp:
            if max_exp is not None:
                if cand_exp <= max_exp:
                    experience_score = 100.0
                else:
                    experience_score = 90.0
            else:
                experience_score = 100.0
        else:
            if min_exp > 0:
                experience_score = (cand_exp / min_exp) * 100.0
            else:
                experience_score = 100.0
            experience_matched = False
            
        if experience_score < 70.0:
            experience_matched = False
    else:
        experience_score = 100.0

    # 4. Location Match (10%)
    req_loc = parsed_reqs["location_lower"]
    if req_loc and req_loc != "not specified":
        location_score = 0.0
        cand_loc = c.get("location_lower", "")
        if req_loc in cand_loc or cand_loc in req_loc:
            location_score = 100.0
        else:
            req_city = parsed_reqs["location_city_lower"]
            cand_city = c.get("location_city_lower", "")
            if req_city and req_city in cand_city:
                location_score = 100.0
            else:
                pref_mode = c.get("preferred_work_mode_lower", "")
                req_mode = parsed_reqs["remote_mode_lower"]
                
                if "remote" in req_mode and "remote" in pref_mode:
                    location_score = 100.0
                elif "hybrid" in req_mode and "flexible" in pref_mode:
                    location_score = 100.0
                elif "flexible" in pref_mode or "remote" in pref_mode:
                    location_score = 50.0
                else:
                    location_score = 20.0
                    
        if location_score < 70.0:
            location_matched = False
    else:
        location_score = 100.0

    # 5. Keyword Match (5%)
    req_kws = parsed_reqs["keywords_lower"]
    if req_kws:
        full_text = c.get("search_keywords_text", "")
        matched_kws = 0
        for kw in req_kws:
            if kw in full_text:
                matched_kws += 1
        keyword_score = (matched_kws / len(req_kws)) * 100.0
    else:
        keyword_score = 100.0

    final_match_score = (
        (role_score * 0.30) +
        (skills_score * 0.45) +
        (experience_score * 0.15) +
        (location_score * 0.10) +
        (keyword_score * 0.05)
    )

    return {
        "score": round(final_match_score, 1),
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "experience_matched": experience_matched,
        "location_matched": location_matched
    }


def _compute_semantic_scores(
    candidates: list[dict],
    jd_emb: np.ndarray | None,
    cand_embs_map: dict,
) -> np.ndarray:
    """
    Build a numpy array of semantic scores (0-1) for a batch of candidates.

    If the candidate's embedding is in the pre-loaded map → use it.
    Otherwise → fall back to 0.5 (neutral; the pipeline will still run).
    """
    scores = []
    for c in candidates:
        cid = c.get("candidate_id", "")
        emb = cand_embs_map.get(cid)
        if emb is not None and jd_emb is not None:
            sim = float(np.dot(emb, jd_emb))
            scores.append(max(0.0, min(1.0, sim)))
        else:
            scores.append(0.5)   # neutral fallback
    return np.array(scores, dtype=float)


def _build_stats(ranked: list[dict], disqualified_count: int) -> StatsResponse:
    """Compute aggregate statistics over a ranked pool for the /stats endpoint."""
    if not ranked:
        return StatsResponse(
            total_ranked=0,
            disqualified_count=disqualified_count,
            avg_capability=0.0,
            avg_trajectory=0.0,
            avg_recruitability=0.0,
            avg_authenticity=0.0,
            avg_notice_period_days=0.0,
            open_to_work_count=0,
            dna_distribution={},
            confidence_distribution={},
            score_buckets={},
            location_distribution=[],
            notice_period_distribution=[],
        )

    caps, trajs, recrs, auths, notices = [], [], [], [], []
    dna_counts: dict[str, int] = defaultdict(int)
    conf_counts: dict[str, int] = defaultdict(int)
    score_buckets: dict[str, int] = defaultdict(int)
    city_counts: dict[str, int] = defaultdict(int)
    notice_buckets = {
        "0–15 days": 0,
        "15–30 days": 0,
        "30–60 days": 0,
        "60+ days": 0,
    }
    open_to_work_count = 0

    bucket_edges = [0.0, 0.2, 0.4, 0.6, 0.8, 1.01]
    bucket_labels = ["0.0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0"]

    for r in ranked:
        caps.append(float(r.get("capability", 0)))

        traj = r.get("trajectory", {})
        trajs.append(float(traj.get("score", 0)) if isinstance(traj, dict) else 0.0)
        dna = traj.get("dna", "Unclear") if isinstance(traj, dict) else "Unclear"
        dna_counts[dna] += 1

        recr = r.get("recruitability", {})
        recrs.append(float(recr.get("score", 0)) if isinstance(recr, dict) else 0.0)

        auth = r.get("authenticity", {})
        auths.append(float(auth.get("score", 0)) if isinstance(auth, dict) else 0.0)

        conf = r.get("confidence", {})
        label = conf.get("label", "Medium") if isinstance(conf, dict) else "Medium"
        conf_counts[label] += 1

        candidate = r.get("candidate", {})
        profile = candidate.get("profile", {})
        signals = candidate.get("redrob_signals", {})

        # Location
        loc = profile.get("location", "")
        city = loc.split(",")[0].strip() if loc else "Unknown"
        city_counts[city] += 1

        notice = signals.get("notice_period_days")
        if notice is not None:
            notices.append(float(notice))
            n = int(notice)
            if n <= 15:
                notice_buckets["0–15 days"] += 1
            elif n <= 30:
                notice_buckets["15–30 days"] += 1
            elif n <= 60:
                notice_buckets["30–60 days"] += 1
            else:
                notice_buckets["60+ days"] += 1

        if signals.get("open_to_work_flag", False):
            open_to_work_count += 1

        fs = float(r.get("final_score", 0))
        for j, upper in enumerate(bucket_edges[1:]):
            if fs < upper:
                score_buckets[bucket_labels[j]] += 1
                break

    def _avg(lst: list) -> float:
        return round(statistics.mean(lst), 2) if lst else 0.0

    # Top 10 cities
    top_cities = sorted(city_counts.items(), key=lambda x: -x[1])[:10]

    return StatsResponse(
        total_ranked=len(ranked),
        disqualified_count=disqualified_count,
        avg_capability=_avg(caps),
        avg_trajectory=_avg(trajs),
        avg_recruitability=_avg(recrs),
        avg_authenticity=_avg(auths),
        avg_notice_period_days=_avg(notices),
        open_to_work_count=open_to_work_count,
        dna_distribution=dict(dna_counts),
        confidence_distribution=dict(conf_counts),
        score_buckets=dict(score_buckets),
        location_distribution=[{"city": city, "count": cnt} for city, cnt in top_cities],
        notice_period_distribution=[
            {"range": k, "count": v} for k, v in notice_buckets.items()
        ],
    )


# ─── ENDPOINTS ────────────────────────────────────────────────────────────────

@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Server health check",
    tags=["Health"],
)
async def health() -> HealthResponse:
    """
    Confirm the server is running and report which assets are loaded.

    Returns:
        HealthResponse with status, version, and loading flags.
    """
    return HealthResponse(
        status="ok",
        version="4.0",
        embeddings_loaded=_state["jd_emb"] is not None,
        distributions_loaded=bool(_state["signal_distributions"]),
        ranked_pool_size=len(_state["ranked_pool"]),
    )


@router.post(
    "/rank",
    response_model=RankResponse,
    summary="Rank a batch of candidates",
    tags=["Ranking"],
)
async def rank_candidates(body: RankRequest) -> RankResponse:
    """
    Score and rank candidates using the 4-dimension FHire pipeline.
    Optimized for in-memory caching, heapq partial sorting, and fast matching.
    """
    import time
    import os
    import heapq
    import re

    is_dev = os.getenv("ENVIRONMENT", "production").lower() == "development"
    t_start = time.perf_counter()

    if not _state["signal_distributions"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Signal distributions not loaded. Restart the server.",
        )

    # ── 1. Resolve candidate list (Retrieval) ──────────────────────────────────
    t_retrieval_start = time.perf_counter()
    if body.candidates:
        if len(body.candidates) > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payload candidates list exceeds maximum allowed size of 100 candidates."
            )
        candidates = body.candidates
        # Ad-hoc precomputation for candidate properties
        for c in candidates:
            if "search_titles" not in c:
                prof = c.get("profile") or {}
                history = c.get("career_history") or []
                skills = c.get("skills") or []
                signals = c.get("redrob_signals") or {}
                titles = {prof.get("current_title", "").lower()}
                for job in history:
                    if job.get("title"):
                        titles.add(job.get("title", "").lower())
                c["search_titles"] = list(filter(None, titles))
                c["current_title_lower"] = prof.get("current_title", "").lower()
                c["search_skills"] = [s.get("name", "").strip().lower() for s in skills if s.get("name")]
                cand_summary = prof.get("summary", "").lower()
                hist_desc = " ".join([h.get("description", "").lower() for h in history if h.get("description")])
                c["search_keywords_text"] = (cand_summary + " " + hist_desc).strip()
                cand_loc = prof.get("location", "")
                c["location_lower"] = cand_loc.lower()
                c["location_city_lower"] = cand_loc.lower().split(",")[0].strip()
                c["preferred_work_mode_lower"] = signals.get("preferred_work_mode", "").lower()
                try:
                    c["total_experience"] = float(prof.get("years_of_experience", 0.0))
                except (ValueError, TypeError):
                    c["total_experience"] = 0.0
    else:
        candidates = _state.get("candidates_cache") or []
        if not candidates:
            # Fallback loading from file if cache is empty
            candidates_path = Path(_state.get("candidates_path", str(_CANDIDATES_JSONL)))
            if not candidates_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="No candidates provided and auto-load file not found."
                )
            with open(candidates_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            candidates.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
            # Precompute fields on fallback
            for c in candidates:
                prof = c.get("profile") or {}
                history = c.get("career_history") or []
                skills = c.get("skills") or []
                signals = c.get("redrob_signals") or {}
                titles = {prof.get("current_title", "").lower()}
                for job in history:
                    if job.get("title"):
                        titles.add(job.get("title", "").lower())
                c["search_titles"] = list(filter(None, titles))
                c["current_title_lower"] = prof.get("current_title", "").lower()
                c["search_skills"] = [s.get("name", "").strip().lower() for s in skills if s.get("name")]
                cand_summary = prof.get("summary", "").lower()
                hist_desc = " ".join([h.get("description", "").lower() for h in history if h.get("description")])
                c["search_keywords_text"] = (cand_summary + " " + hist_desc).strip()
                cand_loc = prof.get("location", "")
                c["location_lower"] = cand_loc.lower()
                c["location_city_lower"] = cand_loc.lower().split(",")[0].strip()
                c["preferred_work_mode_lower"] = signals.get("preferred_work_mode", "").lower()
                try:
                    c["total_experience"] = float(prof.get("years_of_experience", 0.0))
                except (ValueError, TypeError):
                    c["total_experience"] = 0.0
    t_retrieval = time.perf_counter() - t_retrieval_start

    # ── 2. Compute semantic scores & Pipeline scoring ─────────────────────────
    t_semantic_start = time.perf_counter()
    t_pipeline_start = time.perf_counter()
    
    w = body.weights or {
        "capability": 0.40,
        "trajectory": 0.25,
        "recruitability": 0.25,
        "authenticity": 0.10
    }
    w_cap = w.get("capability", 0.40)
    w_traj = w.get("trajectory", 0.25)
    w_recr = w.get("recruitability", 0.25)
    w_auth = w.get("authenticity", 0.10)

    if body.candidates:
        semantic_scores = _compute_semantic_scores(
            candidates,
            _state["jd_emb"],
            _state["cand_embs_map"],
        )
        t_semantic = time.perf_counter() - t_semantic_start
        
        ranked = score_batch(
            candidates=candidates,
            semantic_scores=semantic_scores,
            signal_distributions=_state["signal_distributions"],
            include_counterfactual=body.include_counterfactual,
        )
        t_pipeline = time.perf_counter() - t_pipeline_start
    else:
        t_semantic = 0.0
        ranked = []
        cached_pool = _state.get("ranked_pool") or []
        for r in cached_pool:
            rc = r.copy()
            base = (
                rc["capability"] * w_cap
                + rc["trajectory"]["score"] * w_traj
                + rc["recruitability"]["score"] * w_recr
                + rc["authenticity"]["score"] * w_auth
            ) / 100.0
            rc["final_score"] = base * rc.get("_recruitability_multiplier", 1.0)
            ranked.append(rc)
        t_pipeline = time.perf_counter() - t_pipeline_start

    # ── 4. Requirement matching & score blending ────────────────────────────────
    t_match_start = time.perf_counter()
    reqs = body.requirements
    parsed_reqs = None
    if reqs:
        # Precompute match parameters once per request
        role_lower = reqs.role.strip().lower() if reqs.role else ""
        stopwords = {"senior", "junior", "lead", "staff", "principal", "mid", "developer", "engineer", "and", "or", "to", "for", "in", "of", "with"}
        role_words = [w for w in role_lower.split() if w not in stopwords and len(w) > 1] if role_lower else []
        skills_lower = [s.strip().lower() for s in reqs.skills if s.strip()] if reqs.skills else []
        
        # Pre-compile experience regex patterns
        min_exp = 0.0
        max_exp = None
        if reqs.experience and reqs.experience != "Not specified":
            range_match = re.search(r"(\d+)\s*(?:-|to)\s*(\d+)", reqs.experience)
            plus_match = re.search(r"(\d+)\+", reqs.experience)
            num_match = re.search(r"(\d+)", reqs.experience)
            if range_match:
                min_exp = float(range_match.group(1))
                max_exp = float(range_match.group(2))
            elif plus_match:
                min_exp = float(plus_match.group(1))
            elif num_match:
                min_exp = float(num_match.group(1))
                
        location_lower = reqs.location.strip().lower() if reqs.location else ""
        location_city_lower = location_lower.split(",")[0].strip() if location_lower else ""
        remote_mode_lower = reqs.remoteHybrid.strip().lower() if reqs.remoteHybrid else ""
        keywords_lower = [k.strip().lower() for k in reqs.keywords if k.strip()] if reqs.keywords else []
        
        parsed_reqs = {
            "role_lower": role_lower,
            "role_words": role_words,
            "skills_lower": skills_lower,
            "orig_skills": reqs.skills,
            "min_exp": min_exp,
            "max_exp": max_exp,
            "location_lower": location_lower,
            "location_city_lower": location_city_lower,
            "remote_mode_lower": remote_mode_lower,
            "keywords_lower": keywords_lower,
        }

    for r in ranked:
        cand_dict = r.get("candidate") or {}
        if parsed_reqs:
            match_res = _calculate_requirement_match(cand_dict, parsed_reqs)
            r["requirement_match"] = match_res
            penalty = 0.5 if match_res["score"] < 50.0 else 0.0
            r["final_score"] = (r["final_score"] * 0.9) + (match_res["score"] / 100.0 * 0.1) - penalty
        else:
            r["requirement_match"] = None
    t_match = time.perf_counter() - t_match_start

    # ── 5. Sorting and rank reassignment on the entire pool ─────────────────────
    t_sort_start = time.perf_counter()
    
    # Sort the entire list of ranked candidates by final_score descending
    ranked = sorted(ranked, key=lambda x: (-x["final_score"], x.get("candidate_id", "")))
    
    # Reassign ranks sequentially after sorting the entire pool
    for idx, r in enumerate(ranked):
        r["rank"] = idx + 1
        
    # Only then apply top_n slicing
    top_n = body.top_n or 10
    final_list = ranked[:top_n]
    
    t_sort = time.perf_counter() - t_sort_start

    # ── 6. Serialization ────────────────────────────────────────────────────────
    t_serial_start = time.perf_counter()
    items = [_to_ranked_item(r) for r in final_list]
    t_serial = time.perf_counter() - t_serial_start

    t_total = time.perf_counter() - t_start
    total_disq = len(candidates) - len(ranked)

    # Print profiling logs only in debug/development mode to prevent production spam
    if is_dev:
        logger.info(f"--- PROFILE: /rank completed in {t_total:.4f}s ---")
        logger.info(f"  Retrieval:   {t_retrieval:.4f}s")
        logger.info(f"  Semantic:    {t_semantic:.4f}s")
        logger.info(f"  Pipeline:    {t_pipeline:.4f}s")
        logger.info(f"  Matching:    {t_match:.4f}s")
        logger.info(f"  Sorting:     {t_sort:.4f}s")
        logger.info(f"  Serialization: {t_serial:.4f}s")
        logger.info(f"----------------------------------------------")

    return RankResponse(
        total_scored=len(ranked),
        total_disqualified=total_disq,
        results=items,
    )


@router.get(
    "/candidate/{candidate_id}",
    response_model=CandidateDetailResponse,
    summary="Get full breakdown for one candidate",
    tags=["Candidates"],
)
async def get_candidate(
    candidate_id: str,
    from_source: Optional[str] = None,
    context: Optional[str] = None,
) -> CandidateDetailResponse:
    """
    Return the complete score breakdown for a single candidate by ID.
    Dynamically recalculates recruiter matching context on-the-fly when from_source is "intake" and context is provided.
    """
    import base64
    import json
    import urllib.parse
    import re
    from backend.api.schemas import RequirementSummaryRequest

    # Always retrieve baseline scores from the stable read-only global index
    index = _state["global_ranked_pool_index"]
    r = index.get(candidate_id)

    if r is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found in rankings database.",
        )

    # Make a copy of the candidate score dict to prevent mutating the global startup cache
    rc = r.copy()
    candidate = rc.get("candidate", {})
    profile = candidate.get("profile", {})
    signals = candidate.get("redrob_signals", {})

    reqs = None
    requirement_match_res = None

    if from_source == "intake" and context:
        try:
            # Safe Base64 decoding
            decoded_bytes = base64.b64decode(context)
            decoded_str = urllib.parse.unquote(decoded_bytes.decode("utf-8"))
            context_data = json.loads(decoded_str)
            
            w = context_data.get("weights") or {}
            w_cap = w.get("capability", 0.40)
            w_traj = w.get("trajectory", 0.25)
            w_recr = w.get("recruitability", 0.25)
            w_auth = w.get("authenticity", 0.10)
            
            reqs_dict = context_data.get("requirements")
            if reqs_dict:
                reqs = RequirementSummaryRequest(**reqs_dict)
        except Exception:
            reqs = None

        if reqs:
            # Precompute criteria once for single-candidate match
            role_lower = reqs.role.strip().lower() if reqs.role else ""
            stopwords = {"senior", "junior", "lead", "staff", "principal", "mid", "developer", "engineer", "and", "or", "to", "for", "in", "of", "with"}
            role_words = [w for w in role_lower.split() if w not in stopwords and len(w) > 1] if role_lower else []
            skills_lower = [s.strip().lower() for s in reqs.skills if s.strip()] if reqs.skills else []
            
            min_exp = 0.0
            max_exp = None
            if reqs.experience and reqs.experience != "Not specified":
                range_match = re.search(r"(\d+)\s*(?:-|to)\s*(\d+)", reqs.experience)
                plus_match = re.search(r"(\d+)\+", reqs.experience)
                num_match = re.search(r"(\d+)", reqs.experience)
                if range_match:
                    min_exp = float(range_match.group(1))
                    max_exp = float(range_match.group(2))
                elif plus_match:
                    min_exp = float(plus_match.group(1))
                elif num_match:
                    min_exp = float(num_match.group(1))
                    
            location_lower = reqs.location.strip().lower() if reqs.location else ""
            location_city_lower = location_lower.split(",")[0].strip() if location_lower else ""
            remote_mode_lower = reqs.remoteHybrid.strip().lower() if reqs.remoteHybrid else ""
            keywords_lower = [k.strip().lower() for k in reqs.keywords if k.strip()] if reqs.keywords else []
            
            parsed_reqs = {
                "role_lower": role_lower,
                "role_words": role_words,
                "skills_lower": skills_lower,
                "orig_skills": reqs.skills,
                "min_exp": min_exp,
                "max_exp": max_exp,
                "location_lower": location_lower,
                "location_city_lower": location_city_lower,
                "remote_mode_lower": remote_mode_lower,
                "keywords_lower": keywords_lower,
            }

            requirement_match_res = _calculate_requirement_match(candidate, parsed_reqs)
            rc["requirement_match"] = requirement_match_res
            
            # Recalculate blended score
            base = (
                rc["capability"] * w_cap
                + rc["trajectory"]["score"] * w_traj
                + rc["recruitability"]["score"] * w_recr
                + rc["authenticity"]["score"] * w_auth
            ) / 100.0
            final_score = base * rc.get("_recruitability_multiplier", 1.0)
            
            penalty = 0.5 if requirement_match_res["score"] < 50.0 else 0.0
            final_score = (final_score * 0.9) + (requirement_match_res["score"] / 100.0 * 0.1) - penalty
            rc["final_score"] = final_score

            # Dynamically count how many candidates score higher to calculate the precise rank
            better_count = 0
            cached_pool = _state.get("global_ranked_pool") or []
            for other in cached_pool:
                if other["candidate_id"] == candidate_id:
                    continue
                # calculate other final score
                other_base = (
                    other["capability"] * w_cap
                    + other["trajectory"]["score"] * w_traj
                    + other["recruitability"]["score"] * w_recr
                    + other["authenticity"]["score"] * w_auth
                ) / 100.0
                other_final = other_base * other.get("_recruitability_multiplier", 1.0)
                
                # calculate other requirement match score on-the-fly
                other_cand = other.get("candidate") or {}
                other_match = _calculate_requirement_match(other_cand, parsed_reqs)
                other_penalty = 0.5 if other_match["score"] < 50.0 else 0.0
                other_final = (other_final * 0.9) + (other_match["score"] / 100.0 * 0.1) - other_penalty
                
                # Check if other candidate scores higher (tie-break on candidate_id)
                if other_final > final_score or (abs(other_final - final_score) < 1e-9 and other["candidate_id"] < candidate_id):
                    better_count += 1
                    
            rc["rank"] = better_count + 1
    else:
        rc["requirement_match"] = None

    return CandidateDetailResponse(
        candidate_id=rc["candidate_id"],
        rank=rc.get("rank"),
        final_score=rc["final_score"],
        capability=rc["capability"],
        trajectory=rc["trajectory"],
        recruitability=rc["recruitability"],
        authenticity=rc["authenticity"],
        confidence=rc["confidence"],
        reasoning=rc.get("reasoning", ""),
        counterfactual=rc.get("counterfactual"),
        career_dna=_extract_dna(rc),
        profile=profile,
        signals=signals,
        requirement_match=rc.get("requirement_match"),
    )


@router.post(
    "/compare",
    response_model=CompareResponse,
    summary="Compare two candidates and explain the ranking difference",
    tags=["Comparison"],
)
async def compare(body: CompareRequest) -> CompareResponse:
    """
    Explain why Candidate A ranked above Candidate B.

    Accepts either:
        - Two candidate IDs (looked up from the ranked pool)
        - Two full score dicts (passed directly from the frontend)

    Calls core/comparator.compare_candidates() — no scoring is repeated.

    Args:
        body.candidate_a_id / body.candidate_b_id: IDs to look up.
        body.scores_a / body.scores_b: Direct score dicts (alternative).

    Returns:
        CompareResponse with dimension-wise breakdown and verdict.
    """
    # Resolve score dicts
    if body.scores_a and body.scores_b:
        scores_a = body.scores_a
        scores_b = body.scores_b
    elif body.candidate_a_id and body.candidate_b_id:
        index = _state["global_ranked_pool_index"]
        scores_a = index.get(body.candidate_a_id)
        scores_b = index.get(body.candidate_b_id)

        if scores_a is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Candidate A not found in ranked pool.",
            )
        if scores_b is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Candidate B not found in ranked pool.",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide either (candidate_a_id + candidate_b_id) "
                   "or (scores_a + scores_b).",
        )

    result = compare_candidates(scores_a, scores_b)

    # Build typed dimension comparison list
    dim_comps = [
        DimensionComparison(
            dimension=d["dimension"],
            score_a=d["score_a"],
            score_b=d["score_b"],
            difference=d["difference"],
            advantage=d["advantage"],
            winner=d["winner"],
        )
        for d in result["dimension_comparisons"]
    ]

    def _to_meta(m: dict) -> CandidateMeta:
        return CandidateMeta(
            candidate_id=m.get("candidate_id", ""),
            current_title=m.get("current_title", "Unknown"),
            location=m.get("location", "Unknown"),
            years_of_experience=float(m.get("years_of_experience", 0)),
            career_dna=m.get("career_dna", "Unclear"),
            notice_period=m.get("notice_period"),
            open_to_work=bool(m.get("open_to_work", False)),
            confidence_label=m.get("confidence_label", "Medium"),
        )

    return CompareResponse(
        candidate_a=_to_meta(result["candidate_a"]),
        candidate_b=_to_meta(result["candidate_b"]),
        final_score_a=result["final_score_a"],
        final_score_b=result["final_score_b"],
        final_score_diff=result["final_score_diff"],
        dimension_comparisons=dim_comps,
        dimensions_a_wins=result["dimensions_a_wins"],
        dimensions_b_wins=result["dimensions_b_wins"],
        verdict=result["verdict"],
        reasoning_a=result["reasoning_a"],
        reasoning_b=result["reasoning_b"],
    )


@router.get(
    "/candidates/locations",
    summary="Distinct city list from ranked pool",
    tags=["Candidates"],
)
async def list_locations() -> dict:
    """Return sorted list of unique cities in the ranked pool for filter dropdowns."""
    pool: list[dict] = _state["global_ranked_pool"]
    cities: set[str] = set()
    for r in pool:
        loc = r.get("candidate", {}).get("profile", {}).get("location", "")
        city = loc.split(",")[0].strip()
        if city:
            cities.add(city)
    return {"locations": sorted(cities)}


@router.get(
    "/candidates",
    summary="Paginated, searchable, filterable candidate list",
    tags=["Candidates"],
)
async def list_candidates(
    page: Optional[int] = None,
    page_size: Optional[int] = None,
    limit: int = 50,
    cursor: Optional[str] = None,
    search: str = "",
    location: str = "",
    confidence: str = "",
    career_dna: str = "",
    open_to_work: bool = False,
    min_score: float = 0.0,
    sort_by: str = "rank",
    sort_dir: str = "asc",
) -> dict:
    """
    Return a paginated, filtered, sorted slice of the ranked pool.
    Supports both page-based and cursor-based pagination.
    """
    # ── Validate inputs ───────────────────────────────────────────────────────
    if search and len(search) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query parameter too long. Maximum allowed length is 100 characters."
        )

    allowed_sort_by = {"rank", "final_score", "capability", "trajectory", "recruitability", "authenticity", "notice_period"}
    if sort_by not in allowed_sort_by:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid sort_by parameter. Allowed values: {', '.join(sorted(allowed_sort_by))}"
        )

    allowed_sort_dir = {"asc", "desc"}
    if sort_dir.lower() not in allowed_sort_dir:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid sort_dir parameter. Allowed values: {', '.join(sorted(allowed_sort_dir))}"
        )

    allowed_confidence = {"High", "Medium", "Low"}
    if confidence and confidence not in allowed_confidence:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid confidence parameter. Allowed values: {', '.join(sorted(allowed_confidence))}"
        )

    allowed_dna = {"Startup Builder", "Scale Expert", "Product Engineer", "Research Specialist", "Consulting Only"}
    if career_dna and career_dna not in allowed_dna:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid career_dna parameter. Allowed values: {', '.join(sorted(allowed_dna))}"
        )

    pool: list[dict] = _state["global_ranked_pool"]

    if not pool:
        return {
            "total": 0,
            "items": [],
            "next_cursor": None,
            "has_more": False,
            "page": 1,
            "page_size": limit,
            "total_pages": 0,
            "results": []
        }

    # ── Filter ────────────────────────────────────────────────────────────────
    filtered = pool

    if search:
        sl = search.lower()
        def match_search(r: dict) -> bool:
            cand = r.get("candidate") or {}
            prof = cand.get("profile") or {}
            return (
                sl in r.get("candidate_id", "").lower()
                or sl in prof.get("current_title", "").lower()
                or sl in prof.get("anonymized_name", "").lower()
            )
        filtered = [r for r in filtered if match_search(r)]

    if location:
        def match_loc(r: dict) -> bool:
            cand = r.get("candidate") or {}
            prof = cand.get("profile") or {}
            loc = prof.get("location", "")
            return loc.split(",")[0].strip().lower() == location.lower()
        filtered = [r for r in filtered if match_loc(r)]

    if confidence:
        filtered = [
            r for r in filtered
            if (r.get("confidence") or {}).get("label", "") == confidence
        ]

    if career_dna:
        filtered = [
            r for r in filtered
            if _extract_dna(r) == career_dna
        ]

    if open_to_work:
        def match_otw(r: dict) -> bool:
            cand = r.get("candidate") or {}
            signals = cand.get("redrob_signals") or {}
            return bool(signals.get("open_to_work_flag", False))
        filtered = [r for r in filtered if match_otw(r)]

    if min_score > 0.0:
        filtered = [r for r in filtered if r.get("final_score", 0.0) >= min_score]

    # ── Sort ──────────────────────────────────────────────────────────────────
    reverse = sort_dir.lower() == "desc"

    def _sort_key(r: dict):
        if sort_by == "rank":
            return r.get("rank", 999999)
        if sort_by == "final_score":
            return r.get("final_score", 0.0)
        if sort_by in ("capability", "trajectory", "recruitability", "authenticity"):
            val = r.get(sort_by) or {}
            if isinstance(val, dict):
                return val.get("score", 0.0)
            return float(val) if val is not None else 0.0
        if sort_by == "notice_period":
            cand = r.get("candidate") or {}
            signals = cand.get("redrob_signals") or {}
            return signals.get("notice_period_days", 9999)
        return r.get("rank", 999999)

    filtered = sorted(filtered, key=_sort_key, reverse=reverse)

    # ── Resolve start offset and limit ─────────────────────────────────────────
    final_limit = limit
    if page_size is not None:
        final_limit = page_size
    final_limit = min(max(1, final_limit), 200)

    start_offset = 0
    if cursor:
        try:
            decoded = base64.b64decode(cursor.encode("utf-8")).decode("utf-8")
            cursor_data = json.loads(decoded)
            start_offset = cursor_data.get("offset", 0)
        except Exception:
            start_offset = 0
    elif page is not None:
        start_offset = (page - 1) * final_limit

    total = len(filtered)
    page_items = filtered[start_offset: start_offset + final_limit]

    # Calculate page / total_pages for backward compatibility
    current_page = page if page is not None else (start_offset // final_limit) + 1
    total_pages = max(1, (total + final_limit - 1) // final_limit)

    # Calculate next cursor
    next_offset = start_offset + final_limit
    has_more = next_offset < total
    next_cursor = None
    if has_more:
        try:
            cursor_data = {"offset": next_offset}
            next_cursor = base64.b64encode(json.dumps(cursor_data).encode("utf-8")).decode("utf-8")
        except Exception:
            next_cursor = None

    # ── Shape response ────────────────────────────────────────────────────────
    def _shape(r: dict) -> dict:
        cand = r.get("candidate") or {}
        profile = cand.get("profile") or {}
        signals = cand.get("redrob_signals") or {}
        return {
            "candidate_id": r.get("candidate_id", ""),
            "rank": r.get("rank", 0),
            "final_score": r.get("final_score", 0.0),
            "capability": r.get("capability", 0.0),
            "trajectory": r.get("trajectory", {}),
            "recruitability": r.get("recruitability", {}),
            "authenticity": r.get("authenticity", {}),
            "confidence": r.get("confidence", {}),
            "reasoning": r.get("reasoning", ""),
            "career_dna": _extract_dna(r),
            "title": profile.get("current_title", ""),
            "company": profile.get("current_company", ""),
            "location": profile.get("location", ""),
            "years_of_experience": profile.get("years_of_experience", 0),
            "notice_period_days": signals.get("notice_period_days"),
            "open_to_work": signals.get("open_to_work_flag", False),
            "response_rate": signals.get("recruiter_response_rate", 0.0),
            "github_score": signals.get("github_activity_score"),
            "career_timeline": [
                {
                    "company": h.get("company", ""),
                    "title": h.get("title", ""),
                    "duration_months": h.get("duration_months", 0),
                    "start_date": h.get("start_date", ""),
                    "end_date": h.get("end_date"),
                    "is_current": h.get("is_current", False),
                }
                for h in (cand.get("career_history") or [])
            ],
            "skills": [
                {
                    "name": s.get("name", ""),
                    "proficiency": s.get("proficiency", "intermediate"),
                    "endorsements": s.get("endorsements", 0),
                    "duration_months": s.get("duration_months", 0),
                    "trust_score": (signals.get("skill_assessment_scores") or {}).get(s.get("name", ""), None),
                }
                for s in (cand.get("skills") or [])
            ],
        }

    results = [_shape(r) for r in page_items]

    return {
        "total": total,
        "items": results,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "page": current_page,
        "page_size": final_limit,
        "total_pages": total_pages,
        "results": results,
    }


def _sanitize_csv_cell(val) -> str:
    s = str(val) if val is not None else ""
    if s and s[0] in ('=', '+', '-', '@'):
        return "'" + s
    return s


@router.get(
    "/candidates/export",
    summary="Stream filtered candidate list as a CSV file",
    tags=["Candidates"],
)
async def export_candidates(
    search: str = "",
    location: str = "",
    confidence: str = "",
    career_dna: str = "",
    open_to_work: bool = False,
    min_score: float = 0.0,
    sort_by: str = "rank",
    sort_dir: str = "asc",
    limit: Optional[int] = None,
    selected_ids: Optional[str] = None,
    export_all: bool = False,
):
    """
    Export matching candidates to a CSV file.
    Only streams requested columns.
    """
    # ── Validate inputs ───────────────────────────────────────────────────────
    if search and len(search) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query parameter too long."
        )

    allowed_sort_by = {"rank", "final_score", "capability", "trajectory", "recruitability", "authenticity", "notice_period"}
    if sort_by not in allowed_sort_by:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid sort_by parameter."
        )

    allowed_sort_dir = {"asc", "desc"}
    if sort_dir.lower() not in allowed_sort_dir:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid sort_dir parameter."
        )

    pool: list[dict] = _state["ranked_pool"]
    if not pool:
        # Return empty stream
        def empty_csv():
            yield ""
        return StreamingResponse(empty_csv(), media_type="text/csv")

    # ── Filter ────────────────────────────────────────────────────────────────
    filtered = pool

    if selected_ids:
        # If specific IDs are selected, only export those
        ids_set = {cid.strip() for cid in selected_ids.split(",") if cid.strip()}
        filtered = [r for r in filtered if r.get("candidate_id") in ids_set]
    else:
        # Apply filters
        if search:
            sl = search.lower()
            def match_search_exp(r: dict) -> bool:
                cand = r.get("candidate") or {}
                prof = cand.get("profile") or {}
                return (
                    sl in r.get("candidate_id", "").lower()
                    or sl in prof.get("current_title", "").lower()
                    or sl in prof.get("anonymized_name", "").lower()
                )
            filtered = [r for r in filtered if match_search_exp(r)]

        if location:
            def match_loc_exp(r: dict) -> bool:
                cand = r.get("candidate") or {}
                prof = cand.get("profile") or {}
                loc = prof.get("location", "")
                return loc.split(",")[0].strip().lower() == location.lower()
            filtered = [r for r in filtered if match_loc_exp(r)]

        if confidence:
            filtered = [
                r for r in filtered
                if (r.get("confidence") or {}).get("label", "") == confidence
            ]

        if career_dna:
            filtered = [
                r for r in filtered
                if _extract_dna(r) == career_dna
            ]

        if open_to_work:
            def match_otw_exp(r: dict) -> bool:
                cand = r.get("candidate") or {}
                signals = cand.get("redrob_signals") or {}
                return bool(signals.get("open_to_work_flag", False))
            filtered = [r for r in filtered if match_otw_exp(r)]

        if min_score > 0.0:
            filtered = [r for r in filtered if r.get("final_score", 0.0) >= min_score]

        # ── Sort ──────────────────────────────────────────────────────────────
        reverse = sort_dir.lower() == "desc"

        def _sort_key(r: dict):
            if sort_by == "rank":
                return r.get("rank", 999999)
            if sort_by == "final_score":
                return r.get("final_score", 0.0)
            if sort_by in ("capability", "trajectory", "recruitability", "authenticity"):
                val = r.get(sort_by) or {}
                if isinstance(val, dict):
                    return val.get("score", 0.0)
                return float(val) if val is not None else 0.0
            if sort_by == "notice_period":
                cand = r.get("candidate") or {}
                signals = cand.get("redrob_signals") or {}
                return signals.get("notice_period_days", 9999)
            return r.get("rank", 999999)

        filtered = sorted(filtered, key=_sort_key, reverse=reverse)

    # ── Limit ─────────────────────────────────────────────────────────────────
    if limit is not None and not export_all:
        filtered = filtered[:limit]

    # ── Streaming CSV Generator ────────────────────────────────────────────────
    def iter_csv():
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow([
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
            "Reasoning"
        ])
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        for r in filtered:
            cand = r.get("candidate") or {}
            profile = cand.get("profile") or {}
            signals = cand.get("redrob_signals") or {}
            
            # Safe metrics mapping (Fix 8)
            cap_val = r.get("capability") or 0.0
            cap_score = cap_val.get("score", 0.0) if isinstance(cap_val, dict) else float(cap_val)
            
            traj_val = r.get("trajectory") or {}
            traj_score = traj_val.get("score", 0.0) if isinstance(traj_val, dict) else float(traj_val or 0.0)
            
            rec_val = r.get("recruitability") or {}
            rec_score = rec_val.get("score", 0.0) if isinstance(rec_val, dict) else float(rec_val or 0.0)
            
            auth_val = r.get("authenticity") or {}
            auth_score = auth_val.get("score", 0.0) if isinstance(auth_val, dict) else float(auth_val or 0.0)

            writer.writerow([
                r.get("rank", ""),
                r.get("candidate_id", ""),
                f"{r.get('final_score', 0.0):.3f}",
                _sanitize_csv_cell((r.get("confidence", {}) or {}).get("label", "")),
                _sanitize_csv_cell(profile.get("current_title", "")),
                _sanitize_csv_cell(profile.get("current_company", "")),
                _sanitize_csv_cell(profile.get("location", "")),
                _sanitize_csv_cell(_extract_dna(r)),
                f"{cap_score:.1f}",
                f"{traj_score:.1f}",
                f"{rec_score:.1f}",
                f"{auth_score:.1f}",
                signals.get("notice_period_days", ""),
                "True" if signals.get("open_to_work_flag", False) else "False",
                _sanitize_csv_cell(r.get("reasoning", ""))
            ])
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    headers = {
        'Content-Disposition': 'attachment; filename="talentgraph-export.csv"'
    }
    return StreamingResponse(iter_csv(), media_type="text/csv", headers=headers)


@router.get(
    "/candidates/locations",
    summary="Distinct city list from ranked pool",
    tags=["Candidates"],
)
async def list_locations() -> dict:
    """Return sorted list of unique cities in the ranked pool for filter dropdowns."""
    pool: list[dict] = _state["global_ranked_pool"]
    cities: set[str] = set()
    for r in pool:
        cand = r.get("candidate") or {}
        profile = cand.get("profile") or {}
        loc = profile.get("location", "")
        city = loc.split(",")[0].strip()
        if city:
            cities.add(city)
    return {"locations": sorted(cities)}


@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="Aggregate statistics for the analytics dashboard",
    tags=["Analytics"],
)
async def stats() -> StatsResponse:
    """
    Return aggregate statistics over the current ranked pool.

    Used by the Member 3 analytics dashboard to power charts:
    DNA distribution, confidence distribution, score histogram,
    notice period averages, open-to-work count, etc.

    Returns 200 with zeroed stats if /rank has not been called yet.
    """
    return _build_stats(
        ranked=_state["global_ranked_pool"],
        disqualified_count=_state["global_disqualified_count"],
    )
