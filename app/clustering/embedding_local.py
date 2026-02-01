import os
import logging
import numpy as np
from app.clustering.embedding_base import BaseEmbeddingModel

logger = logging.getLogger(__name__)


class LocalPathEmbeddingModel(BaseEmbeddingModel):
    """Loads any sentence-transformers compatible model from a user-specified path."""

    def __init__(self, model_path):
        if not os.path.isdir(model_path):
            raise ValueError(f"Model path does not exist: {model_path}")
        self._model_path = model_path
        self._model = None

    def _ensure_loaded(self):
        if self._model is None:
            logger.info("Loading local model from %s", self._model_path)
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_path)
            logger.info("Local model loaded successfully")

    def encode(self, texts, batch_size=32):
        self._ensure_loaded()
        embeddings = self._model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            normalize_embeddings=True
        )
        return np.array(embeddings)

    def get_dimension(self):
        self._ensure_loaded()
        return self._model.get_sentence_embedding_dimension()

    @property
    def model_name(self):
        return f"Local model ({os.path.basename(self._model_path)})"
