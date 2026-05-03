import logging
from typing import List, Union
import numpy as np

logger = logging.getLogger("antigravity_k.engine.embeddings")

class EmbeddingEngine:
    def __init__(self):
        self.current_model = None
        self.model = None

    def load_model(self, model_name: str):
        """Load an embedding model via sentence-transformers."""
        # Use a sensible cross-platform default if not provided
        target_model = model_name if model_name else "all-MiniLM-L6-v2"
        
        if self.current_model == target_model and self.model is not None:
            return
            
        logger.info(f"Loading embedding model: {target_model}")
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(target_model)
            self.current_model = target_model
            logger.info("Embedding model loaded successfully.")
        except ImportError:
            logger.error("sentence-transformers is not installed. Falling back to dummy embeddings.")
            self.model = None
            self.current_model = None

    def embed(self, text: Union[str, List[str]], model_name: str) -> List[List[float]]:
        """Generate embeddings for the given text(s)."""
        self.load_model(model_name)
        
        if isinstance(text, str):
            text = [text]
            
        if self.model is not None:
            logger.debug(f"Generating embeddings for {len(text)} items using {self.current_model}")
            embeddings = self.model.encode(text, convert_to_numpy=True)
            return embeddings.tolist()
        else:
            # Fallback dummy embeddings
            logger.warning("Using dummy embeddings because model is not loaded.")
            results = []
            for _ in text:
                vec = np.random.rand(1536) - 0.5
                vec = vec / np.linalg.norm(vec)
                results.append(vec.tolist())
            return results

# Singleton instance
embedding_engine = EmbeddingEngine()

def get_embedding_engine() -> EmbeddingEngine:
    return embedding_engine
