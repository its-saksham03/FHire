#!/usr/bin/env python3
"""
precompute.py — FHire One-Time Offline Precomputation

WHY THIS FILE EXISTS:
  The competition has a HARD CONSTRAINT: rank.py must run in under 5 minutes
  on a CPU-only machine. We cannot compute embeddings for 100,000 candidates
  in 5 minutes — that would take 20+ minutes.

  SOLUTION: Do the heavy work ONCE offline (before submission), save everything
  to disk, then rank.py just loads the pre-saved results = blazing fast.

  This script does TWO things:
    1. Computes embeddings for all 100K candidates + the JD using
       BAAI/bge-small-en-v1.5 (a fast, high-quality embedding model).
       Saves to: data/embeddings.npz

    2. Computes signal distributions across all 100K candidates.
       Used for percentile-based normalization in rank.py.
       Saves to: data/distributions.json

HOW TO RUN:
  python precompute.py --candidates data/candidates.jsonl

  This takes ~15-20 minutes. Run it ONCE. The output files (embeddings.npz,
  distributions.json) are then loaded by rank.py every time it runs.

IMPORTANT:
  - The embedding model downloads automatically first time (~90MB)
  - Needs ~4GB RAM for 100K candidate embeddings in memory
  - Output files: embeddings.npz (~150MB), distributions.json (~2MB)
"""

import json
import argparse
import numpy as np
from pathlib import Path
from tqdm import tqdm

from core.percentile import build_signal_distributions, save_distributions


# ─── JD RICH TEXT ─────────────────────────────────────────────────────────────
# This is NOT just keywords — it's a semantically rich description of what
# the ideal Senior AI Engineer looks like. This is what we embed and compare
# every candidate against.
#
# Why rich text and not just the JD verbatim?
# The JD itself has lots of "company culture" language. We want the embedding
# to focus on the TECHNICAL skills and experience that matter for ranking.

JD_RICH_TEXT = """
Senior AI Engineer information retrieval ranking search production experience.
Semantic search embeddings retrieval augmented generation RAG vector database
hybrid search BM25 dense retrieval FAISS Pinecone Weaviate Qdrant Milvus Elasticsearch.
Fine-tuning LoRA PEFT sentence transformers BGE E5 language models.
NDCG MRR MAP evaluation frameworks learning to rank XGBoost Python.
Product company startup shipped deployed real users queries per second latency serving inference.
NLP information retrieval semantic search recommendation systems.
Embedding drift index refresh retrieval quality regression A/B testing offline evaluation.
Series A AI-native startup talent intelligence platform builder.
Production ML systems built deployed maintained improved scale.
Career trajectory backend search ranking AI engineering growth.
Recruiter response active available immediate joiner short notice India.
"""


# ─── CANDIDATE TEXT BUILDER ───────────────────────────────────────────────────

def build_candidate_text(candidate: dict) -> str:
    """
    Converts a candidate dict into a single text string for embedding.

    We combine:
    - Headline (one-line summary)
    - Professional summary
    - All career descriptions (most important — actual work done)
    - Skill names (for keyword coverage)

    We intentionally EXCLUDE:
    - Certifications (too gameable)
    - Education institution name (not relevant for this seniority level)

    This text is what gets embedded and compared to the JD embedding.
    Higher cosine similarity = more semantically similar to what the JD wants.
    """
    profile = candidate.get("profile", {})

    headline = profile.get("headline", "")
    summary = profile.get("summary", "")

    career_desc = " ".join(
        r.get("description", "")
        for r in candidate.get("career_history", [])
    )

    skills_text = " ".join(
        s.get("name", "")
        for s in candidate.get("skills", [])
    )

    # Title context helps the embedding understand seniority
    title = profile.get("current_title", "")
    yoe = profile.get("years_of_experience", 0)
    title_context = f"{title} {yoe} years experience"

    full_text = f"{title_context} {headline} {summary} {career_desc} {skills_text}".strip()

    # Truncate if very long (embedding models have token limits, but bge-small handles ~512 tokens)
    # ~1500 characters ≈ 300-400 tokens — safe range
    if len(full_text) > 2000:
        full_text = full_text[:2000]

    return full_text


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="FHire — Precompute embeddings and signal distributions"
    )
    parser.add_argument(
        "--candidates", required=True,
        help="Path to candidates.jsonl file"
    )
    parser.add_argument(
        "--out-embeddings", default="data/embeddings.npz",
        help="Output path for embeddings (default: data/embeddings.npz)"
    )
    parser.add_argument(
        "--out-distributions", default="data/distributions.json",
        help="Output path for signal distributions (default: data/distributions.json)"
    )
    parser.add_argument(
        "--model", default="BAAI/bge-small-en-v1.5",
        help="HuggingFace model name for embeddings"
    )
    parser.add_argument(
        "--batch-size", type=int, default=256,
        help="Batch size for embedding computation (default: 256)"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  FHire — Precomputation Script")
    print("=" * 60)

    # ── STEP 1: Load model ────────────────────────────────────────────────────
    print(f"\n[1/5] Loading embedding model: {args.model}")
    print("      (First run will download ~90MB — this is normal)")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(args.model)
    print("      Model loaded successfully")

    # ── STEP 2: Load candidates ───────────────────────────────────────────────
    print(f"\n[2/5] Loading candidates from: {args.candidates}")
    candidates = []
    candidates_path = Path(args.candidates)

    if not candidates_path.exists():
        print(f"ERROR: File not found: {args.candidates}")
        print("Make sure candidates.jsonl is in the data/ folder")
        return

    with open(candidates_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    candidates.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"  Warning: skipping malformed line: {e}")

    print(f"      Loaded {len(candidates):,} candidates")

    # ── STEP 3: Compute JD embedding ─────────────────────────────────────────
    print(f"\n[3/5] Computing Job Description embedding...")
    jd_emb = model.encode(JD_RICH_TEXT.strip(), normalize_embeddings=True)
    print(f"      JD embedding shape: {jd_emb.shape}")

    # ── STEP 4: Compute candidate embeddings ─────────────────────────────────
    print(f"\n[4/5] Computing candidate embeddings...")
    print(f"      Batch size: {args.batch_size}")
    print(f"      This will take ~15-20 minutes. Go get chai ☕")

    texts = []
    for c in tqdm(candidates, desc="      Building texts", unit="candidates"):
        texts.append(build_candidate_text(c))

    print(f"      Built {len(texts):,} candidate texts")
    print(f"      Now encoding (the slow part)...")

    cand_embs = model.encode(
        texts,
        batch_size=args.batch_size,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    print(f"      Embeddings shape: {cand_embs.shape}")

    # ── STEP 5: Save embeddings ───────────────────────────────────────────────
    print(f"\n[5/5] Saving outputs...")

    # Save embeddings
    out_emb_path = Path(args.out_embeddings)
    out_emb_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_emb_path, jd=jd_emb, candidates=cand_embs)
    size_mb = out_emb_path.stat().st_size / (1024 * 1024)
    print(f"      Embeddings saved: {out_emb_path} ({size_mb:.1f} MB)")

    # Compute and save signal distributions
    print(f"      Computing signal distributions across {len(candidates):,} candidates...")
    distributions = build_signal_distributions(candidates)
    save_distributions(distributions, args.out_distributions)

    # ── DONE ──────────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  PRECOMPUTATION COMPLETE")
    print("=" * 60)
    print(f"\n  Files created:")
    print(f"    {args.out_embeddings}")
    print(f"    {args.out_distributions}")
    print(f"\n  Signal distributions computed for: {list(distributions.keys())}")
    print(f"\n  Next step: python rank.py --candidates {args.candidates} --out submission/output.csv")
    print()


if __name__ == "__main__":
    main()
