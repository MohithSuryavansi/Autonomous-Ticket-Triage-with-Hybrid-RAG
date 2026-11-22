"""
evaluation/eval_ragas.py

Official RAGAS framework evaluation using Meta Llama 3.1 (llama3.1:latest) via Ollama.
Uses local BAAI/bge-base-en-v1.5 embeddings for Answer Relevancy (zero VRAM conflict).

Features:
  - Item-by-item incremental checkpointing to {mode}_scored_intermediate.json
  - Auto-resume capability if interrupted (e.g. power cut or crash)
  - Evaluates standard RAGAS metrics:
      * Context Precision
      * Context Recall
      * Faithfulness
      * Answer Relevancy
"""
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from rag_pipeline.config import OLLAMA_BASE_URL, EMBEDDING_MODEL
from rag_pipeline.evaluation.eval_generation import EVALUATION_MODEL

from ragas import evaluate, EvaluationDataset, SingleTurnSample, RunConfig
from ragas.metrics import (
    context_precision,
    context_recall,
    faithfulness,
    answer_relevancy,
)
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from langchain_community.llms import Ollama as LangchainOllama
from langchain_community.embeddings import HuggingFaceEmbeddings


def _build_ragas_llm() -> LangchainLLMWrapper:
    """
    Construct the evaluator LLM wrapper using Llama 3.1 via Ollama.
    """
    lc_llm = LangchainOllama(
        model=EVALUATION_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=0.0,
        timeout=300,
    )
    return LangchainLLMWrapper(lc_llm)


def _build_ragas_embeddings() -> LangchainEmbeddingsWrapper:
    """
    Construct the local BGE bi-encoder embeddings wrapper for Answer Relevancy.
    Runs on CPU to prevent any VRAM collisions with the LLM.
    """
    lc_emb = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    return LangchainEmbeddingsWrapper(lc_emb)


def _save_scored_checkpoint(checkpoint_path: Path, scored_results: List[Dict]) -> None:
    """Save intermediate scored results to disk safely."""
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = checkpoint_path.with_suffix(".tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(scored_results, f, indent=2, ensure_ascii=False)
    temp_path.replace(checkpoint_path)


def evaluate_with_ragas(raw_results: List[Dict], checkpoint_path: Optional[Path] = None) -> List[Dict]:
    """
    Score all raw_results with the official RAGAS framework using Llama 3.1 as the evaluator.
    Supports incremental checkpointing and resuming from intermediate files.

    Args:
        raw_results:     List of generated incident dictionaries from Phase 1.
        checkpoint_path: Optional path to save/resume scored checkpoint.

    Returns:
        List of result dictionaries enriched with individual 'ragas_scores'.
    """
    scored_map: Dict[int, Dict] = {}

    # Check for existing scored checkpoint to resume
    if checkpoint_path and checkpoint_path.exists():
        try:
            with open(checkpoint_path, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, list):
                    for item in saved:
                        idx = item.get("index")
                        if idx is not None and "ragas_scores" in item:
                            scored_map[idx] = item
            if scored_map:
                print(f"[eval_ragas] Found checkpoint at {checkpoint_path.name} with {len(scored_map)}/{len(raw_results)} already scored.")
        except Exception as e:
            print(f"[eval_ragas] WARNING: Could not parse existing scored checkpoint ({e}). Starting fresh.")
            scored_map = {}

    # Check if all samples are already scored
    all_scored = len(raw_results) > 0 and all(r.get("index") in scored_map for r in raw_results)
    if all_scored:
        print(f"[eval_ragas] All {len(raw_results)} samples already scored in checkpoint. Skipping Phase 3 evaluation.")
        return [scored_map[r.get("index")] for r in raw_results]

    print(f"\n{'='*60}")
    print(f"  PHASE 3  |  RAGAS Evaluation with {EVALUATION_MODEL}")
    if checkpoint_path:
        print(f"  Live Checkpoint -> {checkpoint_path.name}")
    print(f"{'='*60}\n")

    ragas_llm = _build_ragas_llm()
    ragas_embs = _build_ragas_embeddings()

    context_precision.llm = ragas_llm
    context_recall.llm = ragas_llm
    faithfulness.llm = ragas_llm
    answer_relevancy.llm = ragas_llm
    answer_relevancy.embeddings = ragas_embs

    metrics = [
        context_precision,
        context_recall,
        faithfulness,
        answer_relevancy,
    ]

    metric_col_map = {
        "context_precision": "context_precision",
        "context_recall": "context_recall",
        "faithfulness": "faithfulness",
        "answer_relevancy": "answer_relevancy",
    }

    run_config = RunConfig(timeout=300, max_retries=2, max_wait=30, max_workers=1)

    scored_results: List[Dict] = []
    for i, r in enumerate(raw_results):
        idx = r.get("index", i)

        # If already scored, use cached result
        if idx in scored_map:
            cached_item = scored_map[idx]
            scored_results.append(cached_item)
            scores = cached_item.get("ragas_scores", {})
            cp = scores.get("context_precision", 0.0)
            cr = scores.get("context_recall", 0.0)
            fa = scores.get("faithfulness", 0.0)
            ar = scores.get("answer_relevancy", 0.0)
            print(
                f"[{i+1:>3}/{len(raw_results)}] (CACHED) "
                f"CP={cp:.4f}  CR={cr:.4f}  F={fa:.4f}  AR={ar:.4f}"
            )
            continue

        # Score single sample
        print(f"[{i+1:>3}/{len(raw_results)}] Scoring {r.get('number', f'Case {i+1}')} with RAGAS...")
        sample = SingleTurnSample(
            user_input=r["query"],
            response=r["generated_answer"],
            retrieved_contexts=r["retrieved_contexts"],
            reference=r["ground_truth"],
        )
        dataset = EvaluationDataset(samples=[sample])

        try:
            results_obj = evaluate(
                dataset=dataset,
                metrics=metrics,
                run_config=run_config,
                batch_size=1,
            )
            scored_df = results_obj.to_pandas()
            row_scores = {}
            for key, col in metric_col_map.items():
                if col in scored_df.columns:
                    val = scored_df.iloc[0][col]
                    try:
                        row_scores[key] = float(val) if val == val else 0.0
                    except (TypeError, ValueError):
                        row_scores[key] = 0.0
                else:
                    row_scores[key] = 0.0
        except Exception as exc:
            print(f"[eval_ragas] WARNING: Error evaluating sample {i+1} ({exc}). Using zero scores.")
            row_scores = {k: 0.0 for k in metric_col_map}

        r["ragas_scores"] = row_scores
        scored_results.append(r)
        scored_map[idx] = r

        cp = row_scores.get("context_precision", 0.0)
        cr = row_scores.get("context_recall", 0.0)
        fa = row_scores.get("faithfulness", 0.0)
        ar = row_scores.get("answer_relevancy", 0.0)
        print(
            f"[{i+1:>3}/{len(raw_results)}] "
            f"CP={cp:.4f}  CR={cr:.4f}  F={fa:.4f}  AR={ar:.4f}"
        )

        # ── LIVE DISK SAVE: Write to tests folder immediately after each scored case ──
        if checkpoint_path:
            _save_scored_checkpoint(checkpoint_path, scored_results)
            print(f"       -> Checkpoint saved ({len(scored_results)}/{len(raw_results)} scored)")

    scored_results.sort(key=lambda x: x.get("index", 0))
    return scored_results
