"""Semantic Prompt Cache — reduce LLM calls via embedding similarity search.

Adapted from: github.com/vivekpathania/ai-experiments (prompt_caching/)
Uses sentence-transformers for semantic similarity matching.
"""

import os
import json
import hashlib
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "prompt_cache")
SIMILARITY_THRESHOLD = 0.85
_model = None


def _get_model():
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Semantic cache model loaded")
        except ImportError:
            logger.warning("sentence-transformers not installed, cache will use exact match only")
    return _model


def _hash_key(prompt: str) -> str:
    return hashlib.md5(prompt.strip().lower().encode()).hexdigest()


def _compute_embedding(text: str):
    model = _get_model()
    if model is None:
        return None
    return model.encode(text)


def _cosine_similarity(a, b) -> float:
    import numpy as np
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def load(prompt: str, use_semantic: bool = True) -> Optional[Dict[str, Any]]:
    key = _hash_key(prompt)
    path = os.path.join(CACHE_DIR, f"{key}.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)

    if not use_semantic:
        return None

    prompt_emb = _compute_embedding(prompt)
    if prompt_emb is None:
        return None

    best_match = None
    best_sim = 0
    os.makedirs(CACHE_DIR, exist_ok=True)

    for fname in os.listdir(CACHE_DIR):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(CACHE_DIR, fname)) as f:
            data = json.load(f)
        cached_emb = _compute_embedding(data.get("prompt", ""))
        if cached_emb is None:
            continue
        sim = _cosine_similarity(prompt_emb, cached_emb)
        if sim > best_sim and sim >= SIMILARITY_THRESHOLD:
            best_sim = sim
            best_match = data

    return best_match


def save(prompt: str, response: str, metadata: Optional[Dict] = None):
    os.makedirs(CACHE_DIR, exist_ok=True)
    key = _hash_key(prompt)
    data = {
        "prompt": prompt,
        "response": response,
        "embedding": _compute_embedding(prompt).tolist() if _get_model() else [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata or {},
    }
    with open(os.path.join(CACHE_DIR, f"{key}.json"), "w") as f:
        json.dump(data, f, indent=2)


def clear():
    if not os.path.exists(CACHE_DIR):
        return
    for fname in os.listdir(CACHE_DIR):
        if fname.endswith(".json"):
            os.remove(os.path.join(CACHE_DIR, fname))
    logger.info("Semantic cache cleared")


def stats() -> Dict[str, Any]:
    if not os.path.exists(CACHE_DIR):
        return {"total_entries": 0, "total_size_bytes": 0}
    total = 0
    size = 0
    for fname in os.listdir(CACHE_DIR):
        if fname.endswith(".json"):
            path = os.path.join(CACHE_DIR, fname)
            total += 1
            size += os.path.getsize(path)
    return {"total_entries": total, "total_size_bytes": size, "cache_dir": CACHE_DIR}
