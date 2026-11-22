# RAGAS Evaluation Framework & Pipeline Architecture

Comprehensive documentation for the automated evaluation suite designed to benchmark retrieval and generation performance across the **Autonomous Incident Intelligence & Ticket Triage System**.

---

## 1. Overview & Objectives

The RAGAS evaluation pipeline provides a rigorous, offline benchmark of the RAG system using **50 curated incident test cases** (`data/test_dataset_ragas_qwen.json`).

It evaluates three distinct retrieval configurations:
1. **Dense-Only Retrieval**: Semantic vector search via ChromaDB + `BAAI/bge-base-en-v1.5`.
2. **Sparse-Only Retrieval**: Lexical keyword search via `BM25Okapi` + ChromaDB metadata enrichment.
3. **Hybrid Retrieval (RRF)**: Reciprocal Rank Fusion combining Dense (Top-15) and Sparse (Top-15).

Evaluation is performed using **DeepSeek-R1 (8B)** as an automated LLM judge via the official **RAGAS 0.4.x** library wrapped with local **Ollama** instances.

```
+-----------------------------------------------------------------------------+
|                             EVALUATION FLOW                                 |
+-----------------------------------------------------------------------------+

  [Test Dataset: 50 Cases]
             |
             v
  [Query Construction] ---> (short_description + description + keywords)
             |
             +----------------------+----------------------+
             v                      v                      v
      [Dense-Only]            [Sparse-Only]            [Hybrid]
     ChromaDB Top-15           BM25 Top-15        Dense Top-15 + Sparse Top-15
             |                      |                      |
             |              (Hydrate Meta)                 v
             |                      |               [RRF Fusion (k=60)]
             +----------------------+----------------------+
                                    |
                                    v
                     [Cross-Encoder Reranker]
                    BAAI/bge-reranker-base (Top-8)
                                    |
                                    v
                         [PHASE 1: Generation]
                      Qwen 3:8B (via Ollama)
                   Plain-text structured analysis
                                    |
                                    v
                        [PHASE 2: VRAM Eviction]
                   ollama.generate(keep_alive=0)
                                    |
                                    v
                         [PHASE 3: Evaluation]
                      DeepSeek-R1 (via RAGAS 0.4)
              4 Metrics: CP, CR, Faithfulness, Relevancy
                                    |
                                    v
                        [JSON Results Export]
            {mode}_results.json (50 entries) & {mode}_summary.json
```

---

## 2. Pipeline Retrieval Configurations

Every pipeline variant standardizes candidate ingestion to feed exactly 8 reranked incidents to the LLM:

| Pipeline | Candidate Stage | Enrichment / Fusion | Reranking Stage | LLM Context |
|---|---|---|---|---|
| **Dense-Only** | Top-15 ChromaDB cosine similarity | Direct metadata lookup | `BAAI/bge-reranker-base` | Top-8 incidents |
| **Sparse-Only** | Top-15 BM25 lexical score | Hydrate metadata + doc from ChromaDB | `BAAI/bge-reranker-base` | Top-8 incidents |
| **Hybrid** | Top-15 Dense + Top-15 Sparse | Reciprocal Rank Fusion (k=60) | `BAAI/bge-reranker-base` | Top-8 incidents |

### Query Construction
To maximize retrieval relevance across both keyword and semantic spaces, search queries are constructed dynamically from the test cases:

```text
Query = Clean(short_description + ". " + description + ". " + " ".join(keywords))
```


---

## 3. Sequential VRAM Memory Management

To run multi-model inference (Generation + LLM Judge) on consumer-grade local hardware without GPU Out-Of-Memory (OOM) errors, the pipeline enforces strict **sequential model lifecycle management**:

1. **Phase 1 (Generation)**:
   - Loads `qwen3:8b` in Ollama.
   - Executes generation across all test cases (1 to N).
   - Collects generated outputs and metadata in memory.

2. **Phase 2 (Explicit VRAM Eviction)**:
   - Dispatches an explicit zero-keepalive call to Ollama:
     ```python
     ollama.generate(model="qwen3:8b", prompt="", keep_alive=0)
     ```
   - Forces Ollama to evict Qwen from GPU VRAM immediately.

3. **Phase 3 (Evaluation)**:
   - Loads `deepseek-r1:8b` in Ollama.
   - Initialises RAGAS LangChain Ollama wrappers.
   - Computes all four RAGAS metrics across the test dataset.

---

## 4. Evaluated RAGAS Metrics

The framework evaluates four primary metrics using **RAGAS 0.4.x**:

### 1. Context Precision
Measures the signal-to-noise ratio of the retrieved incident context. Evaluates whether the ground-truth relevant incidents are ranked higher than irrelevant ones.

### 2. Context Recall
Evaluates whether the retrieved incident context contains all the necessary diagnostic and resolution information present in the ground-truth reference.

### 3. Faithfulness
Measures factual consistency. Assesses whether every claim made in the generated resolution is strictly grounded in the retrieved historical incidents, penalizing hallucinations.

### 4. Answer Relevancy
Evaluates how directly and completely the generated answer addresses the user incident query, without introducing redundant or tangential information.

---

## 5. Directory Structure & Script Responsibilities

All evaluation scripts reside under `rag_pipeline/evaluation/`:

```
rag_pipeline/evaluation/
├── __init__.py
├── eval_generation.py     # Qwen 3:8B stripped generation & Ollama VRAM unload
├── eval_ragas.py          # DeepSeek-R1 RAGAS 0.4.x evaluation wrapper
├── pipeline_runner.py     # Core multi-phase orchestrator & JSON exporter
├── run_dense.py           # CLI entry point for Dense-Only pipeline
├── run_sparse.py          # CLI entry point for Sparse-Only pipeline
├── run_hybrid.py          # CLI entry point for Hybrid (RRF) pipeline
└── results/               # Output directory for generated JSON reports
    ├── dense_results.json
    ├── dense_summary.json
    ├── sparse_results.json
    ├── sparse_summary.json
    ├── hybrid_results.json
    └── hybrid_summary.json
```

---

## 6. CLI Execution Guide

Execute the evaluation pipelines from the repository root:

### Quick Smoke Testing (`--max-samples N`)
Test the entire pipeline on a small subset (e.g., 3 samples) to verify end-to-end functionality:
```bash
# Smoke test Hybrid pipeline
python -m rag_pipeline.evaluation.run_hybrid --max-samples 3

# Smoke test Dense pipeline
python -m rag_pipeline.evaluation.run_dense --max-samples 3

# Smoke test Sparse pipeline
python -m rag_pipeline.evaluation.run_sparse --max-samples 3

# Custom dataset path override (e.g., 50-item dataset)
python -m rag_pipeline.evaluation.run_hybrid --dataset data/test_dataset_ragas_50.json --max-samples 3
```

### Full Benchmark Runs (All 50 Test Cases)
```bash
# Run Full Dense-Only Benchmark
python -m rag_pipeline.evaluation.run_dense

# Run Full Sparse-Only Benchmark
python -m rag_pipeline.evaluation.run_sparse

# Run Full Hybrid (RRF) Benchmark
python -m rag_pipeline.evaluation.run_hybrid
```

---

## 7. Output Formats & Schemas

Results are saved to `rag_pipeline/evaluation/results/`.

### 1. Per-Entry Detailed Results (`{mode}_results.json`)
Contains complete retrieval traces, generated text, RAGAS scores, and ticket triage classification evaluation:
```json
[
  {
    "index": 0,
    "number": "TEST_INC001",
    "query": "BGP Route Flapping Causing Intermittent Packet Drops...",
    "ground_truth": "The root cause was aggressive BGP hold-timer mismatch...",
    "ground_truth_team": "Network Ops",
    "ground_truth_category": "Network",
    "retrieved_context_ids": ["INC00153", "INC00042", "INC00219"],
    "retrieved_contexts": ["--- Incident 1: INC00153..."],
    "retrieved_teams": ["Network Ops", "Network Ops", "Network Ops", "IT Support", "Network Ops"],
    "generated_answer": "Root Causes: 1. Hold timer mismatch on BGP neighbor session...",
    "ragas_scores": {
      "context_precision": 0.8850,
      "context_recall": 0.9200,
      "faithfulness": 0.9500,
      "answer_relevancy": 0.8920
    },
    "triage_evaluation": {
      "ground_truth_team": "Network Ops",
      "predicted_team": "Network Ops",
      "normalized_ground_truth_team": "Network Ops",
      "normalized_predicted_team": "Network Ops",
      "triage_match": true,
      "predicted_priority": "1 - Critical",
      "routing_justification": "Edge router BGP instability impacting inter-DC replication requires Network Operations.",
      "retrieved_teams": ["Network Ops", "Network Ops", "Network Ops", "IT Support", "Network Ops"],
      "retrieval_team_relevance_rate": 0.875
    }
  }
]
```

### 2. Dataset Aggregate Summary (`{mode}_summary.json`)
Comprehensive evaluation summary combining RAGAS benchmarks and operational triage performance:
```json
{
  "mode": "hybrid",
  "n_samples": 50,
  "ragas_metrics": {
    "context_precision": 0.8640,
    "context_recall": 0.8910,
    "faithfulness": 0.9320,
    "answer_relevancy": 0.8870
  },
  "triage_accuracy_analysis": {
    "overall_triage_accuracy": 0.9400,
    "total_correct_triages": 47,
    "total_test_samples": 50,
    "mean_retrieval_team_relevance": 0.8625,
    "triage_accuracy_by_group": {
      "Network Ops": {
        "total_cases": 25,
        "correct_triages": 24,
        "accuracy": 0.9600
      },
      "IT Support": {
        "total_cases": 25,
        "correct_triages": 23,
        "accuracy": 0.9200
      }
    }
  }
}
```