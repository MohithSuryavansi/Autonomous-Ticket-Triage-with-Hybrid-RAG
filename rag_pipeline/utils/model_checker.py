"""
utils/model_checker.py

Two separate checks:
  1. Ollama models (LLM only: qwen3:8b)
     — Ollama requires explicit pull; exits if daemon is not running.
  2. HuggingFace models (embeddings + reranker)
     — sentence-transformers auto-downloads on first use, but we preload
       here so startup failures are caught early and clearly.

Usage:
    python -m rag_pipeline.utils.model_checker
"""
import sys
import subprocess
import requests
from typing import List

_OLLAMA_BASE_URL = "http://localhost:11434"


# ── Ollama helpers ─────────────────────────────────────────────────────────────

def _ollama_is_running(base_url: str = _OLLAMA_BASE_URL) -> bool:
    try:
        r = requests.get(f"{base_url}/api/tags", timeout=5)
        return r.status_code == 200
    except requests.ConnectionError:
        return False


def _list_local_ollama_models(base_url: str = _OLLAMA_BASE_URL) -> List[str]:
    r = requests.get(f"{base_url}/api/tags", timeout=10)
    r.raise_for_status()
    return [m["name"] for m in r.json().get("models", [])]


def _pull_ollama_model(model_name: str) -> None:
    print(f"  [ollama pull] Pulling '{model_name}' — this may take a while...")
    result = subprocess.run(["ollama", "pull", model_name], check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to pull '{model_name}'. Check Ollama logs.")
    print(f"  [ollama pull] '{model_name}' ready.")


def ensure_ollama_models(required: List[str], base_url: str = _OLLAMA_BASE_URL) -> None:
    """
    Ensure all required Ollama models (LLM) are available locally.
    Pulls any that are missing.
    Raises RuntimeError (does NOT exit) if Ollama daemon is not running,
    so the caller can decide whether to abort or just warn.
    """
    if not _ollama_is_running(base_url):
        raise RuntimeError(
            "Ollama is not running.\n"
            "  Start it with: ollama serve\n"
            "  Then restart the backend."
        )

    local_models = _list_local_ollama_models(base_url)
    for model in required:
        base = model.split(":")[0]
        matched = any(
            m == model or m.startswith(base + ":") or m == base
            for m in local_models
        )
        if matched:
            print(f"  [ok] Ollama model '{model}' already available locally.")
        else:
            _pull_ollama_model(model)


# ── HuggingFace helpers ────────────────────────────────────────────────────────

def ensure_hf_models(required: List[str]) -> None:
    """
    Preload HuggingFace models via sentence-transformers.
    Models are downloaded automatically from HuggingFace Hub on first use
    and cached in ~/.cache/huggingface. Calling this at startup surfaces
    download errors early rather than at first query.
    """
    from sentence_transformers import SentenceTransformer, CrossEncoder

    for model_name in required:
        print(f"  [hf] Loading '{model_name}' from HuggingFace Hub (cached after first download)...")
        try:
            # Try as bi-encoder first (embedding models)
            SentenceTransformer(model_name)
            print(f"  [ok] '{model_name}' loaded successfully.")
        except Exception:
            # Fall back to cross-encoder (reranker models)
            try:
                CrossEncoder(model_name)
                print(f"  [ok] '{model_name}' loaded as CrossEncoder.")
            except Exception as e:
                print(f"  [warn] Could not preload '{model_name}': {e}")


# ── Standalone entry-point ─────────────────────────────────────────────────────
if __name__ == "__main__":
    import importlib
    config = importlib.import_module("rag_pipeline.config")

    # Only Ollama needs explicit pre-pull (the LLM)
    OLLAMA_MODELS = [config.LLM_MODEL]

    # HuggingFace models are auto-downloaded by sentence-transformers
    HF_MODELS = [config.EMBEDDING_MODEL, config.RERANKER_MODEL]

    print("[model_checker] Checking Ollama models (LLM)...")
    try:
        ensure_ollama_models(OLLAMA_MODELS, config.OLLAMA_BASE_URL)
    except RuntimeError as e:
        print(f"[model_checker] ERROR: {e}")
        sys.exit(1)

    print("\n[model_checker] Preloading HuggingFace models (embedding + reranker)...")
    ensure_hf_models(HF_MODELS)

    print("\n[model_checker] All models are ready.")

