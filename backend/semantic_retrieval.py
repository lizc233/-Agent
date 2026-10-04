from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

import numpy as np

MODEL_NAME = "BAAI/bge-m3"
DEFAULT_MODEL_CACHE = Path(r"E:\AA_embedding\hub\models--BAAI--bge-m3\snapshots")


def resolve_model_path() -> Path:
    configured = os.getenv("EMBEDDING_MODEL_PATH", "").strip()
    candidates = [Path(configured)] if configured else []
    if DEFAULT_MODEL_CACHE.exists():
        candidates.extend(sorted(DEFAULT_MODEL_CACHE.iterdir(), reverse=True))
    for candidate in candidates:
        if candidate.is_dir() and (candidate / "config.json").exists() and (candidate / "modules.json").exists():
            if (candidate / "model.safetensors").exists() or (candidate / "pytorch_model.bin").exists():
                return candidate.resolve()
    raise FileNotFoundError(
        "未找到本地 bge-m3 模型。请在 .env 中设置 EMBEDDING_MODEL_PATH，"
        "指向包含 config.json、modules.json 和模型权重的 snapshot 文件夹。"
    )


class SemanticRuleIndex:
    def __init__(self, rules: list[dict[str, Any]], cache_dir: Path | None = None) -> None:
        self.rules = rules
        app_root = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
        self.cache_dir = cache_dir or app_root / ".embedding-cache"
        self.model_path = resolve_model_path()
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(str(self.model_path), local_files_only=True)
        self.embeddings = self._load_or_build_embeddings()

    @staticmethod
    def _rule_text(rule: dict[str, Any]) -> str:
        return "\n".join((f"业务类别：{rule['category']}", f"规则标题：{rule['title']}", f"规则内容：{rule['public_content']}", f"处理方式：{rule['answer_strategy']}"))

    def _load_or_build_embeddings(self) -> np.ndarray:
        payload = json.dumps(self.rules, ensure_ascii=False, sort_keys=True).encode("utf-8")
        fingerprint = hashlib.sha256(payload).hexdigest()[:16]
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = self.cache_dir / f"bge-m3-rules-{fingerprint}.npy"
        if cache_path.exists():
            return np.load(cache_path)
        embeddings = self.model.encode([self._rule_text(rule) for rule in self.rules], normalize_embeddings=True, show_progress_bar=False)
        embeddings = np.asarray(embeddings, dtype=np.float32)
        np.save(cache_path, embeddings)
        return embeddings

    def rank(self, question: str, candidate_indices: list[int]) -> list[tuple[float, int]]:
        if not candidate_indices:
            return []
        query = self.model.encode([question], normalize_embeddings=True, show_progress_bar=False)[0]
        scores = self.embeddings[candidate_indices] @ np.asarray(query, dtype=np.float32)
        return sorted(((float(score), index) for score, index in zip(scores, candidate_indices)), reverse=True)
