"""Embeddings module."""

import hashlib
import logging
from typing import Union

import numpy as np

logger = logging.getLogger("antigravity_k.engine.embeddings")


class EmbeddingEngine:
    """Embeddingengine."""

    fallback_dimensions = 1536

    def __init__(self):
        """Initialize the EmbeddingEngine."""
        self.current_model = None
        self.model = None
        self.tokenizer = None

    def initialize(self) -> None:
        """Initialize the engine. Prepares the model for embedding."""
        pass

    def load_model(self, model_name: str):
        """Load an embedding model via sentence-transformers."""
        # Use a sensible cross-platform default if not provided
        target_model = model_name if model_name else "all-MiniLM-L6-v2"

        if self.current_model == target_model and self.model is not None:
            return

        if target_model.startswith(("test-", "mock-", "dummy-")):
            logger.info("Using local fallback embedding model for test target: %s", target_model)
            self.model = None
            self.current_model = target_model
            return

        logger.info("Loading embedding model: %s", target_model)
        try:
            from sentence_transformers import SentenceTransformer

            self.model = SentenceTransformer(target_model)
            self.current_model = target_model
            logger.info("Embedding model loaded successfully.")
        except ImportError:
            logger.error(
                "sentence-transformers is not installed. Falling back to dummy embeddings.",
            )
            self.model = None
            self.current_model = target_model
        except Exception:
            logger.exception(
                "Embedding model '%s' could not be loaded. Falling back to local embeddings.", target_model
            )
            self.model = None
            self.current_model = target_model

    def embed(self, text: Union[str, list[str]], model_name: str) -> list[list[float]]:
        """Generate embeddings for the given text(s)."""
        self.load_model(model_name)

        if isinstance(text, str):
            text = [text]

        if self.model is not None:
            logger.debug(
                "Generating embeddings for %s items using %s",
                len(text),
                self.current_model,
            )
            embeddings = self.model.encode(text, convert_to_numpy=True)
            return embeddings.tolist()
        else:
            logger.warning("Using local fallback embeddings because model is not loaded.")
            return [self._fallback_embedding(item) for item in text]

    def _fallback_embedding(self, text: str) -> list[float]:
        """Deterministic local embedding used when sentence-transformers is unavailable."""
        seed = hashlib.sha256(text.encode("utf-8")).digest()
        chunks: list[float] = []
        counter = 0
        while len(chunks) < self.fallback_dimensions:
            digest = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
            chunks.extend((byte / 127.5) - 1.0 for byte in digest)
            counter += 1
        vec = np.array(chunks[: self.fallback_dimensions], dtype=np.float32)
        norm = np.linalg.norm(vec)
        if norm:
            vec = vec / norm
        return vec.tolist()


# Singleton instance
embedding_engine = EmbeddingEngine()


def get_embedding_engine() -> EmbeddingEngine:
    """Retrieve embedding engine.

    Returns:
        EmbeddingEngine: The embeddingengine result.

    """
    return embedding_engine
