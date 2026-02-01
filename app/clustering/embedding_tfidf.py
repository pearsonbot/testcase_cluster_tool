"""Lightweight TF-IDF based embedding model for testing without sentence-transformers."""

import logging
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from app.clustering.embedding_base import BaseEmbeddingModel

logger = logging.getLogger(__name__)


class TfidfEmbeddingModel(BaseEmbeddingModel):
    """Uses TF-IDF vectors as a lightweight alternative to neural embeddings.
    Suitable for testing and environments where sentence-transformers is not installed.
    """

    def __init__(self):
        self._vectorizer = TfidfVectorizer(
            analyzer='char_wb',
            ngram_range=(2, 4),
            max_features=512,
            sublinear_tf=True,
        )
        self._fitted = False
        self._dimension = 512

    def encode(self, texts, batch_size=32):
        if not texts:
            return np.array([]).reshape(0, self._dimension)

        if not self._fitted:
            matrix = self._vectorizer.fit_transform(texts)
            self._fitted = True
            self._dimension = matrix.shape[1]
        else:
            matrix = self._vectorizer.transform(texts)

        result = matrix.toarray().astype(np.float32)

        # L2 normalize
        norms = np.linalg.norm(result, axis=1, keepdims=True)
        result = result / np.maximum(norms, 1e-10)

        return result

    def get_dimension(self):
        return self._dimension

    @property
    def model_name(self):
        return "TF-IDF (lightweight test mode)"
