#!/usr/bin/env python3
"""
rank.py — FHire Main Ranking Engine

WHY THIS FILE EXISTS:
  This is THE file that gets timed and judged. It must:
    - Complete in under 5 minutes on CPU
    - Produce exactly 100 ranked candidates
    - Make ZERO API calls (no Gemini, GPT, Claude, nothing)
    - Output a valid CSV with reasoning filled for all 100 rows

HOW IT WORKS:
  1. Load pre-computed embeddings (embeddings.npz) — instant, just numpy load
  2. Load signal distributions (distributions.json) — instant, just JSON load
  3. Load all 100K candidates from candidates.jsonl
  4. Compute semantic similarities — ONE numpy matrix multiply (< 1 second for 100K)
  5. For each candidate:
       a. Run disqualifier — fast binary checks
       b. If passes: compute all 4 dimension scores
  6. Sort by final score, take top 100
  7. Generate reasoning for top 100
  8. Write CSV

  Most of the "intelligence" is in the scoring engines.
  rank.py is just the orchestrator that calls them all.

USAGE:
  python rank.py --candidates data/candidates.jsonl --out submission/output.csv

OUTPUT CSV FORMAT:
  candidate_id, rank, score, reasoning
  CAND_0012345, 1, 0.847234, ML Engineer with 7.0yrs; career DNA: Startup Builder; at Redrob: built production RAG...
"""

import json
import csv
import argparse
import time
import numpy as np
from pathlib import Path

from core.disqualifier import is_disqualified
from core.capability_engine import capability_score
from core.trajectory_engine import trajectory_score_final
from core.percentile import load_distributions

# Try to import Member 2's engines (fallback stubs are in pipeline.py)
try:
    from core.pipeline import score_candidate
    _USE_PIPELINE = True
except ImportError:
    _USE_PIPELINE = False

# Try direct imports of Member 2's engines
try:
    from core.recruitability_engine import recruitability_score_and_multiplier
    _HAS_RECR = True
except ImportError:
    _HAS_RECR = False

try:
    from core.authenticity_engine import authenticity_score
    _HAS_AUTH = True
except ImportError:
    _HAS_AUTH = False

try:
    from core.confidence_engine import confidence_score
    _HAS_CONF = True
except ImportError:
    _HAS_CONF = False

try:
    from core.reasoning_generator import generate_reasoning
    _HAS_REASON = True
except ImportError:
    _HAS_REASON = False

try:
    from core.counterfactual import what_would_it_take
    _HAS_CF = True
except ImportError:
    _HAS_CF = False

# Import stubs from pipeline (always available)
from core.pipeline import (
    _stub_recruitability,
    _stub_authenticity,
    _stub_confidence,
    _stub_reasoning,
    TODAY,
)


# ─── FAST SCORING HELPERS ─────────────────────────────────────────────────────

def _get_recruitability(candidate, signal_distributions):
    if _HAS_RECR:
        return recruitability_score_and_multiplier(candidate, signal_distributions)
    return _stub_recruitability(candidate, signal_distributions)


def _get_authenticity(candidate):
    if _HAS_AUTH:
        return authenticity_score(candidate)
    return _stub_authenticity(candidate)


def _get_confidence(candidate, cap, traj, recr, auth):
    if _HAS_CONF:
        return confidence_score(candidate, cap, traj, recr, auth)
    return _stub_confidence(candidate, cap, traj, recr, auth)


def _get_reasoning(candidate, scores, rank):
    if _HAS_REASON:
        return generate_reasoning(candidate, scores, rank)
    return _stub_reasoning(candidate, scores, rank)


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    start_time = time.time()

    parser = argparse.ArgumentParser(
        description="FHire — Rank 100,000 candidates and output top 100"
    )
    parser.add_argument("--candidates", required=True, help="Path to candidates.jsonl")
    parser.add_argument("--out", required=True, help="Output CSV path")
    parser.add_argument("--embeddings", default="data/embeddings.npz", help="Pre-computed embeddings")
    parser.add_argument("--distributions", default="data/distributions.json", help="Signal distributions")
    parser.add_argument("--top-n", type=int, default=100, help="Number of candidates to output")
    args = parser.parse_args()

    print("=" * 60)
    print("  FHire — Ranking Engine")
    print("=" * 60)

    # ── STEP 1: Load pre-computed embeddings ──────────────────────────────────
    print(f"\n[1/8] Loading embeddings from {args.embeddings}...")
    emb_path = Path(args.embeddings)
    if not emb_path.exists():
        print(f"ERROR: Embeddings not found: {args.embeddings}")
        print("Run precompute.py first: python precompute.py --candidates data/candidates.jsonl")
        return

    emb_data = np.load(args.embeddings)
    jd_emb = emb_data["jd"]           # Shape: (embed_dim,)
    cand_embs = emb_data["candidates"] # Shape: (100000, embed_dim)
    print(f"      Embeddings loaded: {cand_embs.shape[0]:,} candidates, dim={cand_embs.shape[1]}")

    # ── STEP 2: Load signal distributions ────────────────────────────────────
    print(f"\n[2/8] Loading signal distributions from {args.distributions}...")
    dist_path = Path(args.distributions)
    if not dist_path.exists():
        print(f"ERROR: Distributions not found: {args.distributions}")
        print("Run precompute.py first.")
        return

    signal_distributions = load_distributions(args.distributions)
    print(f"      Distributions loaded: {len(signal_distributions)} signals")

    # ── STEP 3: Load candidates ───────────────────────────────────────────────
    print(f"\n[3/8] Loading candidates from {args.candidates}...")
    candidates = []
    with open(args.candidates, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    candidates.append(json.loads(line))
                except json.JSONDecodeError:
                    pass  # Skip malformed lines silently

    n_total = len(candidates)
    print(f"      Loaded {n_total:,} candidates")

    # Validate embedding count matches candidate count
    if cand_embs.shape[0] != n_total:
        print(f"WARNING: Embedding count ({cand_embs.shape[0]:,}) != candidate count ({n_total:,})")
        print("         Using min of the two. Re-run precompute.py if counts differ significantly.")
        n_use = min(cand_embs.shape[0], n_total)
        candidates = candidates[:n_use]
        cand_embs = cand_embs[:n_use]

    # ── STEP 4: Compute semantic similarities (ONE fast matrix multiply) ──────
    print(f"\n[4/8] Computing semantic similarities (fast numpy dot product)...")
    t4 = time.time()
    # Both embeddings are L2-normalized (normalize_embeddings=True in precompute.py)
    # so dot product = cosine similarity directly
    # Result: shape (n_candidates,), values 0.0 to 1.0
    semantic_sims = (cand_embs @ jd_emb).clip(0.0, 1.0)
    semantic_scores_arr = semantic_sims * 100.0  # Scale to 0-100
    print(f"      Done in {time.time() - t4:.2f}s — shape: {semantic_scores_arr.shape}")

    # ── STEP 5: Score all candidates ──────────────────────────────────────────
    print(f"\n[5/8] Scoring {n_total:,} candidates...")
    print(f"      Running disqualifier + 4-dimension scoring...")
    t5 = time.time()

    results = []
    disqualified_count = 0
    disq_reasons = {}

    for i, candidate in enumerate(candidates):

        # Print progress every 10,000 candidates
        if i > 0 and i % 10000 == 0:
            elapsed = time.time() - t5
            rate = i / elapsed
            eta = (n_total - i) / rate
            print(f"      Progress: {i:,}/{n_total:,} ({i/n_total*100:.0f}%) — ETA: {eta:.0f}s")

        # ── Hard filter first ─────────────────────────────────────────────────
        disq, reason = is_disqualified(candidate)
        if disq:
            disqualified_count += 1
            category = reason.split(":")[0] if reason else "unknown"
            disq_reasons[category] = disq_reasons.get(category, 0) + 1
            continue

        # ── Dimension 1: Capability ───────────────────────────────────────────
        sem_score = float(semantic_scores_arr[i])
        cap = capability_score(candidate, sem_score)

        # ── Dimension 2: Trajectory ───────────────────────────────────────────
        traj = trajectory_score_final(candidate)

        # ── Dimension 3: Recruitability (MULTIPLICATIVE) ──────────────────────
        recr = _get_recruitability(candidate, signal_distributions)

        # ── Dimension 4: Authenticity ─────────────────────────────────────────
        auth = _get_authenticity(candidate)

        # ── Base Score ────────────────────────────────────────────────────────
        base = (
            cap             * 0.40
            + traj["score"] * 0.25
            + recr["score"] * 0.25
            + auth["score"] * 0.10
        ) / 100.0

        # ── Final Score = base × recruitability multiplier ────────────────────
        # MULTIPLICATIVE: inactive/unresponsive candidate gets multiplier 0.1
        # → score tanks to 10% regardless of capability
        final_score = base * recr["multiplier"]

        # ── Confidence ────────────────────────────────────────────────────────
        conf = _get_confidence(candidate, cap, traj, recr, auth)

        results.append({
            "candidate_id":             candidate.get("candidate_id", ""),
            "final_score":              final_score,
            "capability":               cap,
            "trajectory":               traj,
            "recruitability":           recr,
            "authenticity":             auth,
            "confidence":               conf,
            "candidate":                candidate,
            "_recruitability_multiplier": recr["multiplier"],
        })

    scoring_time = time.time() - t5
    print(f"\n      Scoring complete in {scoring_time:.1f}s")
    print(f"      Total: {n_total:,} | Disqualified: {disqualified_count:,} | Scored: {len(results):,}")
    print(f"      Disqualification breakdown: {disq_reasons}")

    # ── STEP 6: Sort and select top N ─────────────────────────────────────────
    print(f"\n[6/8] Sorting {len(results):,} qualified candidates...")
    # Sort: primary = final_score descending, secondary = candidate_id for determinism
    results.sort(key=lambda x: (-x["final_score"], x["candidate_id"]))
    top_n = results[:args.top_n]
    print(f"      Selected top {len(top_n)} candidates")

    # Verify no irrelevant titles in top 10 (safety check)
    IRRELEVANT_CHECK = ["hr manager", "accountant", "content writer", "marketing manager",
                        "civil engineer", "mechanical engineer", "graphic designer", "sales executive"]
    top_10_issues = []
    for r in top_n[:10]:
        title = r["candidate"].get("profile", {}).get("current_title", "").lower()
        if any(t in title for t in IRRELEVANT_CHECK):
            top_10_issues.append(f"  WARNING: '{title}' in top 10 — check disqualifier!")

    if top_10_issues:
        print("\n" + "\n".join(top_10_issues))
    else:
        print("      ✓ Top 10 sanity check passed — no irrelevant titles")

    # ── STEP 7: Generate reasoning and counterfactuals ────────────────────────
    print(f"\n[7/8] Generating reasoning for top {len(top_n)}...")
    all_final_scores = [r["final_score"] for r in results]

    for i, r in enumerate(top_n):
        rank = i + 1
        r["rank"] = rank
        r["reasoning"] = _get_reasoning(r["candidate"], r, rank)

        # Counterfactual (only if module available)
        if _HAS_CF:
            try:
                r["counterfactual"] = what_would_it_take(
                    r["candidate"], r["final_score"], rank,
                    all_final_scores, signal_distributions
                )
            except Exception:
                r["counterfactual"] = None
        else:
            r["counterfactual"] = None

    # ── STEP 8: Write CSV ─────────────────────────────────────────────────────
    print(f"\n[8/8] Writing submission CSV to {args.out}...")
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        for r in top_n:
            writer.writerow([
                r["candidate_id"],
                r["rank"],
                f"{r['final_score']:.6f}",
                r["reasoning"],
            ])

    total_time = time.time() - start_time

    # ── FINAL SUMMARY ─────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"  ✓ DONE — FHire Ranking Complete")
    print("=" * 60)
    print(f"\n  Output: {args.out}")
    print(f"  Total runtime: {total_time:.1f}s ({total_time/60:.1f} min)")
    print(f"  {'✓ WITHIN 5 MINUTE LIMIT' if total_time < 300 else '✗ EXCEEDED 5 MINUTE LIMIT'}")
    print(f"\n  Top 5 candidates:")
    for r in top_n[:5]:
        cid = r["candidate_id"]
        score = r["final_score"]
        title = r["candidate"].get("profile", {}).get("current_title", "?")
        dna = r["trajectory"].get("dna", "?")
        conf = r["confidence"].get("label", "?")
        print(f"    #{r['rank']:>3} {cid} | {score:.4f} | {title} | DNA: {dna} | Conf: {conf}")

    print(f"\n  Score range: {top_n[0]['final_score']:.4f} → {top_n[-1]['final_score']:.4f}")
    print(f"\n  Run validate_submission.py to verify the output CSV.")
    print()


if __name__ == "__main__":
    main()
