"""
evaluation/run_hybrid.py

Hybrid evaluation pipeline CLI entry point.
Retrieval: Dense top-15 + Sparse top-15 -> RRF -> Cross-Encoder reranker -> top-8 -> Generate & Evaluate.

Usage:
    python -m rag_pipeline.evaluation.run_hybrid
    python -m rag_pipeline.evaluation.run_hybrid --max-samples 5
    python -m rag_pipeline.evaluation.run_hybrid --dataset data/test_dataset_ragas_50.json
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from rag_pipeline.evaluation.pipeline_runner import run_full_pipeline

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hybrid RAG evaluation pipeline.")
    parser.add_argument("--max-samples", type=int, default=None,
                        help="Limit to N test cases (default: all).")
    parser.add_argument("--dataset", type=str, default=None,
                        help="Path to custom test dataset JSON file.")
    args = parser.parse_args()
    run_full_pipeline(mode="hybrid", max_samples=args.max_samples, dataset_path=args.dataset)
