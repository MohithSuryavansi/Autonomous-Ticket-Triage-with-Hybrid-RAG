"""
evaluation/run_sparse.py

Sparse-Only evaluation pipeline CLI entry point.
Retrieval: BM25 top-15 -> metadata from ChromaDB -> Cross-Encoder reranker -> top-8 -> Generate & Evaluate.

Usage:
    python -m rag_pipeline.evaluation.run_sparse
    python -m rag_pipeline.evaluation.run_sparse --max-samples 5
    python -m rag_pipeline.evaluation.run_sparse --dataset data/test_dataset_ragas_50.json
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from rag_pipeline.evaluation.pipeline_runner import run_full_pipeline

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sparse-Only RAG evaluation pipeline.")
    parser.add_argument("--max-samples", type=int, default=None,
                        help="Limit to N test cases (default: all).")
    parser.add_argument("--dataset", type=str, default=None,
                        help="Path to custom test dataset JSON file.")
    args = parser.parse_args()
    run_full_pipeline(mode="sparse", max_samples=args.max_samples, dataset_path=args.dataset)
