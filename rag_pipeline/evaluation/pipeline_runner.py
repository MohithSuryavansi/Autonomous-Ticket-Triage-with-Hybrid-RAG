"""
evaluation/pipeline_runner.py

Shared retrieval, orchestration, and evaluation for all three pipelines.

Features:
  - Dynamic dataset path resolution (supports --dataset CLI override)
  - Incremental live checkpointing to rag_pipeline/tests/{mode}_generated_intermediate.json
    (saves every single generated answer to disk immediately upon completion)
  - Auto-resume capability (skips already generated test cases if checkpoint exists)
  - Dense / Sparse / Hybrid retrieval (top-15 per retriever)
  - Sparse metadata enrichment via ChromaDB
  - Cross-encoder reranking to top-8
  - Phase 1: Qwen generation across all test cases with live disk saving
  - Phase 2: VRAM unload of Qwen (via keep_alive=0)
  - Phase 3: RAGAS scoring via DeepSeek-R1 (CP, CR, Faithfulness, Relevancy)
  - Phase 4: Triage & Retrieval Accuracy Evaluation:
      * Predicted Assignment Group vs Ground Truth Team match
      * Per-group triage accuracy (Network Ops vs IT Support)
      * Top-8 retrieved contexts team relevance rate
  - Rich JSON reporting (saved to both rag_pipeline/evaluation/results/ and rag_pipeline/tests/)

Usage:
    from rag_pipeline.evaluation.pipeline_runner import run_full_pipeline
    run_full_pipeline(mode="hybrid", max_samples=5)
"""
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

import chromadb

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from rag_pipeline.config import (
    TEST_DATASET_FILE,
    CHROMA_PERSIST_DIR,
    CHROMA_COLLECTION_NAME,
    DENSE_TOP_K,
    SPARSE_TOP_K,
    RERANK_TOP_N,
)
from rag_pipeline.processing.query_preprocessing import preprocess_query
from rag_pipeline.processing.cross_encoder_reranking import rerank
from rag_pipeline.evaluation.eval_generation import (
    generate_eval_answer,
    unload_generation_model,
    GENERATION_MODEL,
    EVALUATION_MODEL,
)

EVAL_TOP_K    = 20
EVAL_RERANK_N = 5

# Output Directories
RESULTS_DIR = Path(__file__).resolve().parent / "results"
TESTS_DIR   = Path(__file__).resolve().parents[1] / "tests"


# ── Team Normalization Helper ─────────────────────────────────────────────────

def _normalize_team(team_str: str) -> str:
    """Normalize team strings for robust comparison."""
    if not team_str:
        return "Unknown"
    s = team_str.strip().lower()
    if any(k in s for k in ["network", "netops", "infra", "noc"]):
        return "Network Ops"
    if any(k in s for k in ["support", "helpdesk", "desktop", "service desk", "it"]):
        return "IT Support"
    if any(k in s for k in ["database", "dba"]):
        return "Database Admin"
    return team_str.strip()


# ── Query construction ────────────────────────────────────────────────────────

def _build_query(tc: Dict) -> str:
    """
    Construct the search query from test case fields.
    Concatenates: short_description + description + keywords (space-joined).
    Then runs through the standard query preprocessor.
    """
    short  = tc.get("short_description", "")
    desc   = tc.get("description", "")
    kws    = tc.get("keywords", [])
    kw_str = " ".join(kws) if isinstance(kws, list) else str(kws)
    raw    = f"{short}. {desc}. {kw_str}"
    return preprocess_query(raw)


# ── Sparse metadata enrichment ────────────────────────────────────────────────

def _enrich_sparse_hits(hits: List[Dict], collection) -> List[Dict]:
    """
    BM25 sparse retriever only returns {id, score}.
    Fetch full metadata + document text from ChromaDB so the cross-encoder
    has passage text available for scoring.
    """
    ids = [h["id"] for h in hits]
    if not ids:
        return hits
    results = collection.get(ids=ids, include=["metadatas", "documents"])
    meta_map = {
        doc_id: {"metadata": meta, "document": doc}
        for doc_id, meta, doc in zip(
            results["ids"], results["metadatas"], results["documents"]
        )
    }
    enriched = []
    for h in hits:
        extra = meta_map.get(h["id"], {"metadata": {}, "document": ""})
        enriched.append({
            "id":       h["id"],
            "score":    h["score"],
            "metadata": extra["metadata"],
            "document": extra["document"],
        })
    return enriched


# ── Retriever factory ─────────────────────────────────────────────────────────

def _build_retriever(mode: str):
    if mode == "dense":
        from rag_pipeline.retrieval.dense_retrieval import DenseRetriever
        return DenseRetriever()
    elif mode == "sparse":
        from rag_pipeline.retrieval.sparse_retrieval import SparseRetriever
        return SparseRetriever()
    else:
        from rag_pipeline.retrieval.hybrid_retrieval import HybridRetriever
        return HybridRetriever()


def _retrieve(mode: str, retriever, query: str, collection) -> List[Dict]:
    if mode == "dense":
        return retriever.search(query, top_k=EVAL_TOP_K)
    elif mode == "sparse":
        raw_hits = retriever.search(query, top_k=EVAL_TOP_K)
        return _enrich_sparse_hits(raw_hits, collection)
    else:
        return retriever.search(query, dense_top_k=EVAL_TOP_K, sparse_top_k=EVAL_TOP_K)


def _format_context_for_ragas(r: Dict) -> str:
    """
    Format a retrieved incident into complete context including resolution
    so RAGAS (Llama 3.1) evaluates faithfulness and recall against the full runbook.
    """
    doc = r.get("document", "").strip()
    meta = r.get("metadata", {})
    resolution = meta.get("resolution", "").strip()
    component = meta.get("affected_component", "").strip()

    parts = [doc]
    if component and f"Component: {component}" not in doc:
        parts.append(f"Affected Component: {component}")
    if resolution:
        parts.append(f"Resolution: {resolution}")
    return "\n".join(parts)


# ── Incremental Checkpoint Helper ─────────────────────────────────────────────

def _save_checkpoint(checkpoint_path: Path, raw_results: List[Dict]) -> None:
    """Save intermediate results to disk safely."""
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = checkpoint_path.with_suffix(".tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(raw_results, f, indent=2, ensure_ascii=False)
    temp_path.replace(checkpoint_path)


# ── Phase 1: Generation & Retrieval (With Live Incremental Saving) ────────────

def generate_all(mode: str, test_cases: List[Dict], checkpoint_path: Optional[Path] = None) -> List[Dict]:
    """
    Phase 1: Retrieve + Generate answers with Qwen across test cases.
    Saves each completed result immediately to disk in TESTS_DIR so no progress is ever lost.
    """
    if checkpoint_path is None:
        TESTS_DIR.mkdir(parents=True, exist_ok=True)
        checkpoint_path = TESTS_DIR / f"{mode}_generated_intermediate.json"

    raw_results = []
    completed_indices = set()

    # Check for existing checkpoint to resume
    if checkpoint_path.exists():
        try:
            with open(checkpoint_path, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, list) and len(saved) > 0:
                    raw_results = saved
                    completed_indices = {r.get("index") for r in raw_results if "index" in r}
                    print(f"[pipeline_runner] Found checkpoint at {checkpoint_path.name} with {len(raw_results)} completed cases.")
        except Exception as e:
            print(f"[pipeline_runner] WARNING: Could not parse existing checkpoint ({e}). Starting fresh.")
            raw_results = []
            completed_indices = set()

    # Check if all requested samples are already generated
    if len(completed_indices) >= len(test_cases):
        print(f"\n{'='*60}")
        print(f"  PHASE 1  |  Mode: {mode.upper()}  |  Answer Generation with {GENERATION_MODEL}")
        print(f"  [SKIPPED] All {len(test_cases)}/{len(test_cases)} test cases already generated in checkpoint.")
        print(f"{'='*60}\n")
        return raw_results[:len(test_cases)]

    print(f"\n{'='*60}")
    print(f"  PHASE 1  |  Mode: {mode.upper()}  |  Answer Generation with {GENERATION_MODEL}")
    print(f"  Live Checkpoint -> {checkpoint_path.name}")
    print(f"{'='*60}\n")

    client     = chromadb.PersistentClient(path=str(CHROMA_PERSIST_DIR))
    collection = client.get_collection(CHROMA_COLLECTION_NAME)
    retriever  = _build_retriever(mode)

    for idx, tc in enumerate(test_cases):
        if idx in completed_indices:
            print(f"[{idx+1:>3}/{len(test_cases)}] Case {tc.get('number', idx)} already in checkpoint. Skipping...")
            continue

        query        = _build_query(tc)
        ground_truth = tc.get("ground_truth", "")
        gt_team      = tc.get("assignment_group", "")
        gt_cat       = tc.get("category", "")
        tc_num       = tc.get("number", f"TEST_INC{idx+1:03d}")

        print(f"[{idx+1:>3}/{len(test_cases)}] Retrieving & generating for {tc_num} ({gt_team})...")

        candidates = _retrieve(mode, retriever, query, collection)
        reranked   = rerank(query, candidates, top_n=EVAL_RERANK_N)
        answer, structured = generate_eval_answer(query, reranked)

        # Extract retrieved teams from top-5 reranked incidents
        retrieved_teams = [
            r.get("metadata", {}).get("assignment_group", "Unknown")
            for r in reranked
        ]

        entry = {
            "index":                 idx,
            "number":                tc_num,
            "query":                 query,
            "ground_truth":          ground_truth,
            "ground_truth_team":     gt_team,
            "ground_truth_category": gt_cat,
            "urgency":               tc.get("urgency"),
            "impact":                tc.get("impact"),
            "retrieved_context_ids": [r["id"] for r in reranked],
            "retrieved_contexts":    [_format_context_for_ragas(r) for r in reranked],
            "retrieved_teams":       retrieved_teams,
            "generated_answer":      answer,
            "structured":            structured,
        }

        raw_results.append(entry)
        completed_indices.add(idx)

        # ── LIVE DISK SAVE: Write to tests folder immediately on each query ──
        _save_checkpoint(checkpoint_path, raw_results)
        print(f"       -> Saved to {checkpoint_path.name} ({len(raw_results)}/{len(test_cases)} done)")

    raw_results.sort(key=lambda x: x.get("index", 0))
    return raw_results


# ── Phase 2: VRAM Unload ──────────────────────────────────────────────────────

def unload_generation() -> None:
    """Phase 2: Evict Qwen from VRAM before loading Llama 3.1."""
    print(f"\n{'='*60}")
    print(f"  PHASE 2  |  VRAM Cleanup & Memory Management")
    print(f"{'='*60}\n")
    unload_generation_model()


# ── Phase 3: RAGAS Scoring ────────────────────────────────────────────────────

def score_with_ragas(mode: str, raw_results: List[Dict]) -> List[Dict]:
    """Phase 3: Score results with RAGAS (Llama 3.1 as LLM judge)."""
    from rag_pipeline.evaluation.eval_ragas import evaluate_with_ragas
    scored_checkpoint = TESTS_DIR / f"{mode}_scored_intermediate.json"
    return evaluate_with_ragas(raw_results, checkpoint_path=scored_checkpoint)


# ── Phase 4: Triage & Retrieval Accuracy Analysis ─────────────────────────────

def compute_triage_and_retrieval_analysis(scored_results: List[Dict]) -> Dict:
    """
    Evaluate team routing / triage accuracy and retrieval group relevance.
    """
    total = len(scored_results)
    if total == 0:
        return {}

    correct_triage = 0
    group_stats = {}
    total_retrieval_relevance = 0.0

    for r in scored_results:
        gt_team   = _normalize_team(r.get("ground_truth_team", ""))
        pred_team = _normalize_team(r.get("structured", {}).get("predicted_team", ""))

        is_match = (gt_team == pred_team)
        if is_match:
            correct_triage += 1

        # Track per-group stats
        if gt_team not in group_stats:
            group_stats[gt_team] = {"total": 0, "correct": 0}
        group_stats[gt_team]["total"] += 1
        if is_match:
            group_stats[gt_team]["correct"] += 1

        # Retrieval context team relevance rate (% of top-8 matching ground truth team)
        ret_teams = [_normalize_team(t) for t in r.get("retrieved_teams", [])]
        match_count = sum(1 for t in ret_teams if t == gt_team)
        ret_relevance_rate = match_count / len(ret_teams) if ret_teams else 0.0
        total_retrieval_relevance += ret_relevance_rate

        # Store in row
        r["triage_evaluation"] = {
            "ground_truth_team":             r.get("ground_truth_team", ""),
            "predicted_team":                r.get("structured", {}).get("predicted_team", ""),
            "normalized_ground_truth_team":  gt_team,
            "normalized_predicted_team":     pred_team,
            "triage_match":                  is_match,
            "predicted_priority":            r.get("structured", {}).get("predicted_priority", ""),
            "routing_justification":         r.get("structured", {}).get("routing_justification", ""),
            "retrieved_teams":               r.get("retrieved_teams", []),
            "retrieval_team_relevance_rate": round(ret_relevance_rate, 4),
        }

    overall_triage_accuracy = round(correct_triage / total, 4)
    mean_retrieval_relevance = round(total_retrieval_relevance / total, 4)

    group_accuracy_breakdown = {}
    for g, stat in group_stats.items():
        acc = round(stat["correct"] / stat["total"], 4) if stat["total"] > 0 else 0.0
        group_accuracy_breakdown[g] = {
            "total_cases":     stat["total"],
            "correct_triages": stat["correct"],
            "accuracy":        acc,
        }

    return {
        "overall_triage_accuracy":       overall_triage_accuracy,
        "total_correct_triages":         correct_triage,
        "total_test_samples":            total,
        "mean_retrieval_team_relevance": mean_retrieval_relevance,
        "triage_accuracy_by_group":      group_accuracy_breakdown,
    }


# ── Output Saver ──────────────────────────────────────────────────────────────

def save_results(mode: str, scored_results: List[Dict], triage_metrics: Dict) -> None:
    """Save per-entry results JSON and aggregate summary JSON to both results/ and tests/."""
    print(f"\n{'='*60}")
    print(f"  PHASE 4  |  Triage Analysis & Report Generation")
    print(f"{'='*60}\n")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    TESTS_DIR.mkdir(parents=True, exist_ok=True)

    per_entry = [
        {
            "index":                 r["index"],
            "number":                r.get("number", f"TEST_INC{r['index']+1:03d}"),
            "query":                 r["query"],
            "ground_truth":          r["ground_truth"],
            "ground_truth_team":     r.get("ground_truth_team", ""),
            "ground_truth_category": r.get("ground_truth_category", ""),
            "retrieved_context_ids": r["retrieved_context_ids"],
            "retrieved_contexts":    r["retrieved_contexts"],
            "retrieved_teams":       r.get("retrieved_teams", []),
            "generated_answer":      r["generated_answer"],
            "ragas_scores":          r.get("ragas_scores", {}),
            "triage_evaluation":     r.get("triage_evaluation", {}),
        }
        for r in scored_results
    ]

    # Save to rag_pipeline/evaluation/results/
    results_path = RESULTS_DIR / f"{mode}_results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(per_entry, f, indent=2, ensure_ascii=False)

    # Also save copy to rag_pipeline/tests/
    tests_results_path = TESTS_DIR / f"{mode}_results.json"
    with open(tests_results_path, "w", encoding="utf-8") as f:
        json.dump(per_entry, f, indent=2, ensure_ascii=False)

    print(f"[pipeline_runner] Detailed results saved to:")
    print(f"  -> {results_path}")
    print(f"  -> {tests_results_path}")

    # Aggregate RAGAS metrics
    ragas_keys = ["context_precision", "context_recall", "faithfulness", "answer_relevancy"]
    ragas_agg = {}
    for m in ragas_keys:
        vals = [
            r["ragas_scores"][m]
            for r in scored_results
            if r.get("ragas_scores") and r["ragas_scores"].get(m) is not None
        ]
        ragas_agg[m] = round(sum(vals) / len(vals), 4) if vals else None

    summary = {
        "mode":                     mode,
        "n_samples":                len(scored_results),
        "ragas_metrics":            ragas_agg,
        "triage_accuracy_analysis": triage_metrics,
    }

    summary_path = RESULTS_DIR / f"{mode}_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    tests_summary_path = TESTS_DIR / f"{mode}_summary.json"
    with open(tests_summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # ── Console Report ────────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"  EVALUATION SUMMARY  |  Mode: {mode.upper()}  |  Samples: {len(scored_results)}")
    print(f"{'='*70}")
    print("\n  [RAGAS METRICS]")
    for m in ragas_keys:
        val = ragas_agg.get(m)
        print(f"    - {m:<22}: {val:.4f}" if val is not None else f"    - {m:<22}: N/A")

    print("\n  [TRIAGE & RETRIEVAL ACCURACY ANALYSIS]")
    triage_acc = triage_metrics.get("overall_triage_accuracy", 0.0)
    correct_cnt = triage_metrics.get("total_correct_triages", 0)
    total_cnt   = triage_metrics.get("total_test_samples", 0)
    ret_rel     = triage_metrics.get("mean_retrieval_team_relevance", 0.0)

    print(f"    - Overall Triage Accuracy      : {triage_acc*100:.2f}% ({correct_cnt}/{total_cnt} correct)")
    print(f"    - Mean Retrieved Team Relevance: {ret_rel*100:.2f}% of top-8 matches GT team")

    print("\n  [PER-ASSIGNMENT GROUP ACCURACY BREAKDOWN]")
    for grp, st in triage_metrics.get("triage_accuracy_by_group", {}).items():
        g_acc = st.get("accuracy", 0.0) * 100
        print(f"    - {grp:<16}: {g_acc:>6.2f}% ({st.get('correct_triages')}/{st.get('total_cases')})")

    print(f"\n  Results JSON -> {results_path}")
    print(f"  Summary JSON -> {summary_path}")
    print(f"{'='*70}\n")


# ── Full Pipeline Entry Point ─────────────────────────────────────────────────

def run_full_pipeline(mode: str, max_samples: Optional[int] = None, dataset_path: Optional[str] = None) -> None:
    """
    Execute the full evaluation pipeline for the given mode.

    Phases:
      1. Load test cases (from dataset_path or default TEST_DATASET_FILE)
      2. Phase 1: Retrieve + Generate answers with Qwen (with live per-query saving to tests/)
      3. Phase 2: Unload Qwen from VRAM
      4. Phase 3: Score with RAGAS (llama3.1:latest as LLM judge + local BGE embeddings)
      5. Phase 4: Compute Triage & Retrieval Accuracy Analysis
      6. Save detailed & summary JSON reports to both results/ and tests/
    """
    if dataset_path:
        target_file = Path(dataset_path)
    else:
        target_file = Path(TEST_DATASET_FILE)

    if not target_file.exists():
        for alt in ["test_dataset_ragas_50.json", "test_dataset_ragas_qwen.json", "test_dataset_ragas_40.json"]:
            alt_path = target_file.parent / alt
            if alt_path.exists():
                target_file = alt_path
                break

    with open(target_file, "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    if max_samples:
        test_cases = test_cases[:max_samples]
        print(f"[pipeline_runner] Limited to {max_samples} samples for this run.")

    print(f"[pipeline_runner] Loaded {len(test_cases)} test cases from {target_file.name}")

    checkpoint_file = TESTS_DIR / f"{mode}_generated_intermediate.json"
    raw_results    = generate_all(mode, test_cases, checkpoint_path=checkpoint_file)
    unload_generation()
    scored_results = score_with_ragas(mode, raw_results)
    triage_metrics = compute_triage_and_retrieval_analysis(scored_results)
    save_results(mode, scored_results, triage_metrics)
