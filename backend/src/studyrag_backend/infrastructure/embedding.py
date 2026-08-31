from hashlib import sha256
from pathlib import Path
from threading import Lock
from typing import cast

import numpy as np
import torch
from sentence_transformers import CrossEncoder, SentenceTransformer


class EmbeddingService:
    """Lazy local embedding model shared by one API or worker process."""

    def __init__(
        self,
        *,
        model_name: str,
        revision: str,
        dimension: int,
        query_prefix: str,
        passage_prefix: str,
        device: str,
        batch_size: int,
        cache_dir: Path,
    ) -> None:
        self.model_name = model_name
        self.revision = revision
        self.dimension = dimension
        self.query_prefix = query_prefix
        self.passage_prefix = passage_prefix
        self.requested_device = device
        self.batch_size = batch_size
        self.cache_dir = cache_dir
        self._model: SentenceTransformer | None = None

    @property
    def device(self) -> str:
        if self.requested_device == "auto":
            return "cuda" if torch.cuda.is_available() else "cpu"
        return self.requested_device

    def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._model = SentenceTransformer(
                self.model_name,
                device=self.device,
                cache_folder=str(self.cache_dir),
                revision=self.revision,
            )
            model_dimension = self._model.get_embedding_dimension()
            if model_dimension != self.dimension:
                raise RuntimeError(
                    f"embedding dimension mismatch: configured={self.dimension}, "
                    f"model={model_dimension}"
                )
        return self._model

    def _encode(self, values: list[str]) -> list[list[float]]:
        if not values:
            return []
        encoded = self._get_model().encode(
            values,
            batch_size=self.batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        array: np.ndarray = encoded
        if array.ndim != 2 or array.shape[1] != self.dimension:
            raise RuntimeError("embedding model returned an unexpected vector shape")
        return cast(list[list[float]], array.astype(float).tolist())

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._encode([f"{self.passage_prefix}{text}" for text in texts])

    def embed_query(self, query: str) -> list[float]:
        return self._encode([f"{self.query_prefix}{query}"])[0]

    def token_offsets(self, text: str) -> list[tuple[int, int]]:
        model = self._get_model()
        encoded = model.tokenizer(
            text,
            add_special_tokens=False,
            return_offsets_mapping=True,
            truncation=False,
        )
        offsets = encoded.get("offset_mapping")
        if offsets is None:
            raise RuntimeError("embedding tokenizer does not provide offset mappings")
        return [(int(start), int(end)) for start, end in offsets if int(end) > int(start)]

    @property
    def signature(self) -> str:
        source = (
            f"{self.model_name}:{self.revision}:{self.dimension}:"
            f"{self.query_prefix}:{self.passage_prefix}:normalize=true"
        )
        return sha256(source.encode("utf-8")).hexdigest()


class EmbeddingRegistry:
    """Cache models by their immutable vector-space signature."""

    def __init__(
        self,
        *,
        device: str,
        batch_size: int,
        cache_dir: Path,
    ) -> None:
        self.device = device
        self.batch_size = batch_size
        self.cache_dir = cache_dir
        self._services: dict[str, EmbeddingService] = {}
        self._rerankers: dict[str, CrossEncoder] = {}
        self._lock = Lock()

    def get(
        self,
        *,
        model_name: str,
        revision: str,
        dimension: int,
        query_prefix: str,
        passage_prefix: str,
    ) -> EmbeddingService:
        candidate = EmbeddingService(
            model_name=model_name,
            revision=revision,
            dimension=dimension,
            query_prefix=query_prefix,
            passage_prefix=passage_prefix,
            device=self.device,
            batch_size=self.batch_size,
            cache_dir=self.cache_dir,
        )
        with self._lock:
            return self._services.setdefault(candidate.signature, candidate)

    def rerank(self, model_name: str, query: str, documents: list[str]) -> list[float]:
        if not documents:
            return []
        with self._lock:
            model = self._rerankers.get(model_name)
            if model is None:
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                model = CrossEncoder(
                    model_name,
                    device=self.device if self.device != "auto" else None,
                    cache_dir=str(self.cache_dir),
                )
                self._rerankers[model_name] = model
        scores = model.predict([(query, document) for document in documents])
        array = np.asarray(scores, dtype=float).reshape(-1)
        # Cross-encoder output ranges differ. A sigmoid gives the UI a stable 0..1 score.
        normalized = 1.0 / (1.0 + np.exp(-array))
        return cast(list[float], normalized.tolist())
