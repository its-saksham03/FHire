"""
backend/main.py — FHire FastAPI Application Entry Point

Responsibilities:
    - Create the FastAPI app instance
    - Register the API router
    - Load embeddings and distributions ONCE at startup (fast, from disk)
    - Auto-rank all candidates at startup so GET /api/candidates is ready immediately
    - Expose app for uvicorn

Usage:
    uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

Environment variables (optional):
    EMBEDDINGS_PATH     Path to embeddings.npz (default: data/embeddings.npz)
    DISTRIBUTIONS_PATH  Path to distributions.json (default: data/distributions.json)
    CANDIDATES_PATH     Path to candidates.jsonl (default: data/candidates.jsonl)
    ALLOWED_ORIGINS     Comma-separated list of allowed CORS origins
                        (default: http://localhost:3000 — never use * in production)
    ENVIRONMENT         "development" or "production" (controls docs exposure)
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import numpy as np
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.routes import get_state, router

logger = logging.getLogger("talentgraph")
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")

# Default asset paths (override via environment variables)
_DEFAULT_EMBEDDINGS = "data/embeddings.npz"
_DEFAULT_DISTRIBUTIONS = "data/distributions.json"
_DEFAULT_CANDIDATES = "data/candidates.jsonl"

VERSION = "4.0"
TITLE = "FHire — AI Recruiter Intelligence Engine"
DESCRIPTION = (
    "We don't rank resumes. We rank hiring decisions.\n\n"
    "4-dimension candidate scoring with counterfactual explainability, "
    "career trajectory analysis, and recruiter-grade reasoning."
)

# ─── ENVIRONMENT ──────────────────────────────────────────────────────────────

ENVIRONMENT = os.getenv("ENVIRONMENT", "production").lower()
IS_PRODUCTION = ENVIRONMENT == "production"

# CORS: never allow wildcard with credentials in production.
# Set ALLOWED_ORIGINS="https://yourdomain.com" in production.
_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:3001")
ALLOWED_ORIGINS: list[str] = [o.strip() for o in _raw_origins.split(",") if o.strip()]


# ─── STARTUP / SHUTDOWN ───────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI lifespan handler — runs startup logic before the server accepts
    requests, and cleanup on shutdown.
    """
    state = get_state()

    # ── Automatically download assets if missing ─────────────────────────────
    try:
        from backend.utils.download_assets import check_and_download_all_assets
        check_and_download_all_assets()
    except Exception as e:
        logger.critical(f"Asset check/download failed at startup: {e}")
        import sys
        sys.exit(1)

    embeddings_path = Path(os.getenv("EMBEDDINGS_PATH", _DEFAULT_EMBEDDINGS))
    distributions_path = Path(os.getenv("DISTRIBUTIONS_PATH", _DEFAULT_DISTRIBUTIONS))
    candidates_path = Path(os.getenv("CANDIDATES_PATH", _DEFAULT_CANDIDATES))
    state["candidates_path"] = str(candidates_path)
    state["candidates_cache"] = []

    # ── Load signal distributions ─────────────────────────────────────────────
    if distributions_path.exists():
        logger.info(f"Loading distributions: {distributions_path}")
        with open(distributions_path, encoding="utf-8") as f:
            state["signal_distributions"] = json.load(f)
        logger.info(
            f"Distributions loaded — {len(state['signal_distributions'])} signals"
        )
    else:
        logger.warning(
            f"Distributions file not found: {distributions_path}. "
            "Percentile scoring will be degraded. Run precompute.py first."
        )

    # ── Load candidates and precompute lookup index fields ────────────────────
    candidates_cache = []
    if candidates_path.exists():
        logger.info(f"Loading and indexing candidates from {candidates_path}…")
        try:
            with open(candidates_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        c = json.loads(line)
                        prof = c.get("profile") or {}
                        history = c.get("career_history") or []
                        skills = c.get("skills") or []
                        signals = c.get("redrob_signals") or {}

                        # Precompute titles list for role matching
                        titles = {prof.get("current_title", "").lower()}
                        for job in history:
                            if job.get("title"):
                                titles.add(job.get("title", "").lower())
                        c["search_titles"] = list(filter(None, titles))
                        c["current_title_lower"] = prof.get("current_title", "").lower()

                        # Precompute skills list
                        c_skills = {s.get("name", "").strip().lower() for s in skills if s.get("name")}
                        c["search_skills"] = list(filter(None, c_skills))

                        # Precompute keywords text
                        cand_summary = prof.get("summary", "").lower()
                        hist_desc = " ".join([h.get("description", "").lower() for h in history if h.get("description")])
                        c["search_keywords_text"] = (cand_summary + " " + hist_desc).strip()

                        # Precompute location and preferred work mode
                        cand_loc = prof.get("location", "")
                        c["location_lower"] = cand_loc.lower()
                        c["location_city_lower"] = cand_loc.lower().split(",")[0].strip()
                        c["preferred_work_mode_lower"] = signals.get("preferred_work_mode", "").lower()

                        # Precompute years of experience float representation
                        try:
                            c["total_experience"] = float(prof.get("years_of_experience", 0.0))
                        except (ValueError, TypeError):
                            c["total_experience"] = 0.0

                        candidates_cache.append(c)
                    except json.JSONDecodeError:
                        pass
            state["candidates_cache"] = candidates_cache
            logger.info(f"Loaded and indexed {len(candidates_cache):,} candidates successfully.")
        except OSError as exc:
            logger.warning(f"Could not load candidates from {candidates_path}: {exc}")
    else:
        logger.warning(f"Candidates file not found: {candidates_path}")

    # ── Load embeddings ───────────────────────────────────────────────────────
    if embeddings_path.exists():
        logger.info(f"Loading embeddings: {embeddings_path}")
        emb_data = np.load(embeddings_path)
        state["jd_emb"] = emb_data["jd"]          # shape (embed_dim,)
        cand_embs = emb_data["candidates"]          # shape (N, embed_dim)
        logger.info(
            f"Embeddings loaded — {cand_embs.shape[0]:,} candidates, "
            f"dim={cand_embs.shape[1]}"
        )

        # Build candidate_id → embedding vector map using cached candidates
        cand_embs_map: dict = {}
        for idx, c in enumerate(candidates_cache):
            cid = c.get("candidate_id", "")
            if cid and idx < cand_embs.shape[0]:
                cand_embs_map[cid] = cand_embs[idx]
        state["cand_embs_map"] = cand_embs_map
        logger.info(f"Embedding index built — {len(cand_embs_map):,} entries")
    else:
        logger.warning(
            "Embeddings file not found. "
            "Semantic similarity will default to 0.5 per candidate. "
            "Run precompute.py first for accurate rankings."
        )

    logger.info(f"FHire backend v{VERSION} ready.")

    # ── Auto-rank all candidates at startup ───────────────────────────────────
    if candidates_cache and state["signal_distributions"]:
        logger.info("Auto-ranking all candidates at startup…")
        try:
            from core.pipeline import score_batch as _score_batch  # noqa: PLC0415

            _sem_scores = []
            for _c in candidates_cache:
                _cid = _c.get("candidate_id", "")
                _emb = state["cand_embs_map"].get(_cid)
                if _emb is not None and state["jd_emb"] is not None:
                    _sim = float(np.dot(_emb, state["jd_emb"]))
                    _sem_scores.append(max(0.0, min(1.0, _sim)))
                else:
                    _sem_scores.append(0.5)

            _ranked = _score_batch(
                candidates=candidates_cache,
                semantic_scores=np.array(_sem_scores, dtype=float),
                signal_distributions=state["signal_distributions"],
                include_counterfactual=False,
            )
            state["ranked_pool"] = _ranked
            state["ranked_pool_index"] = {r["candidate_id"]: r for r in _ranked}
            state["disqualified_count"] = len(candidates_cache) - len(_ranked)
            
            # Populate stable Global Ranking Cache (never modified by recruiter searches)
            state["global_ranked_pool"] = _ranked
            state["global_ranked_pool_index"] = state["ranked_pool_index"].copy()
            state["global_disqualified_count"] = state["disqualified_count"]
            
            logger.info(
                f"Startup ranking complete — scored: {len(_ranked):,}, "
                f"disqualified: {state['disqualified_count']:,}"
            )
        except Exception as _exc:  # noqa: BLE001
            logger.warning(
                f"Startup auto-rank failed: {_exc}. "
                "Call POST /api/rank to populate the ranked pool."
            )
    else:
        logger.info(
            "Skipping startup auto-rank (candidates or distributions not available). "
            "Call POST /api/rank to populate the ranked pool."
        )

    yield
    # Shutdown — nothing to clean up (no DB connections, no files open)
    logger.info("FHire backend shutting down.")


# ─── APP FACTORY ──────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    # In production, disable Swagger/ReDoc to prevent API schema exposure.
    # Set ENVIRONMENT=production to disable.
    # EXPOSE_DOCS environment variable can enable Swagger docs if not in production.
    expose_docs = os.getenv("EXPOSE_DOCS", "false").lower() == "true"
    if IS_PRODUCTION:
        expose_docs = False  # Never expose in production

    docs_url = "/docs" if expose_docs else None
    redoc_url = "/redoc" if expose_docs else None
    openapi_url = "/openapi.json" if expose_docs else None

    app = FastAPI(
        title=TITLE,
        description=DESCRIPTION,
        version=VERSION,
        lifespan=lifespan,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )

    # ── Rate limiting tracker ──────────────────────────────────────────────────
    RATE_LIMIT_WINDOW = 60  # seconds
    GLOBAL_RATE_LIMIT = 60   # requests per minute per IP
    RANK_RATE_LIMIT = 10     # requests per minute per IP for /api/rank

    global_rate_tracker: dict[str, list[float]] = defaultdict(list)
    rank_rate_tracker: dict[str, list[float]] = defaultdict(list)

    # ── Request size limit & rate limiting middleware ──────────────────────────
    MAX_REQUEST_SIZE = 5 * 1024 * 1024  # 5MB limit

    @app.middleware("http")
    async def security_and_rate_limiting_middleware(request: Request, call_next):
        # 1. Enforce payload size limit (Content-Length check)
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > MAX_REQUEST_SIZE:
                    return JSONResponse(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        content={"detail": "Request payload too large (max 5MB)"}
                    )
            except ValueError:
                pass

        # 2. Rate limiting check
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        # Global rate limit
        global_rate_tracker[client_ip] = [t for t in global_rate_tracker[client_ip] if now - t < RATE_LIMIT_WINDOW]
        if len(global_rate_tracker[client_ip]) >= GLOBAL_RATE_LIMIT:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."}
            )
        global_rate_tracker[client_ip].append(now)

        # /api/rank rate limit
        if request.url.path in ("/api/rank", "/api/rank/"):
            rank_rate_tracker[client_ip] = [t for t in rank_rate_tracker[client_ip] if now - t < RATE_LIMIT_WINDOW]
            if len(rank_rate_tracker[client_ip]) >= RANK_RATE_LIMIT:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded for ranking. Maximum 10 requests per minute."}
                )
            rank_rate_tracker[client_ip].append(now)

        return await call_next(request)

    # ── CORS ──────────────────────────────────────────────────────────────────
    # SECURITY: allow_origins=["*"] combined with allow_credentials=True is
    # explicitly forbidden by the CORS spec and rejected by browsers.
    # Enable allow_credentials only if there is no wildcard.
    has_wildcard = "*" in ALLOWED_ORIGINS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o for o in ALLOWED_ORIGINS if o != "*"] if has_wildcard else ALLOWED_ORIGINS,
        allow_credentials=not has_wildcard,   # credentials=True requires explicit origins, never wildcard
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Accept"],
    )

    # ── Security headers middleware ────────────────────────────────────────────
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):  # type: ignore[misc]
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        response.headers["Permissions-Policy"] = "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()"
        
        # CSP: strict by default, relaxed conditionally for development Swagger UI
        path = request.url.path
        if expose_docs and (path.startswith("/docs") or path.startswith("/redoc") or path.startswith("/openapi.json")):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data: https://fastapi.tiangolo.com; "
                "frame-ancestors 'none'"
            )
        else:
            response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; sandbox"

        # Remove server fingerprinting header
        if "server" in response.headers:
            del response.headers["server"]
        return response

    # Mount all API routes under /api prefix
    app.include_router(router, prefix="/api")

    return app


# ─── ENTRY POINT ──────────────────────────────────────────────────────────────

app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=not IS_PRODUCTION,  # Never reload in production
        log_level="info",
    )
