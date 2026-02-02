import logging
import time
import numpy as np
from app.clustering.embedding_base import BaseEmbeddingModel

logger = logging.getLogger(__name__)


class BuiltinEmbeddingModel(BaseEmbeddingModel):
    """Loads bge-large-zh-v1.5 from the bundled models/ directory."""

    def __init__(self, model_path):
        self._model_path = model_path
        self._model = None

    def _ensure_loaded(self):
        if self._model is None:
            logger.info("Loading built-in model from %s", self._model_path)
            t0 = time.time()
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_path)
            load_time = time.time() - t0

            device = str(self._model.device) if hasattr(self._model, 'device') else 'unknown'
            dim = self._model.get_sentence_embedding_dimension()
            logger.info("Built-in model loaded in %.2fs, device=%s, dim=%d",
                         load_time, device, dim)

    def encode(self, texts, batch_size=32):
        self._ensure_loaded()
        total = len(texts)
        total_batches = (total + batch_size - 1) // batch_size

        if total_batches <= 1:
            t0 = time.time()
            embeddings = self._model.encode(
                texts, batch_size=batch_size,
                show_progress_bar=False, normalize_embeddings=True
            )
            logger.debug("Encoded %d texts in %.2fs", total, time.time() - t0)
            return np.array(embeddings)

        all_embeddings = []
        encode_start = time.time()

        for i in range(0, total, batch_size):
            batch = texts[i:i + batch_size]
            batch_num = i // batch_size + 1
            t0 = time.time()

            embeddings = self._model.encode(
                batch, batch_size=batch_size,
                show_progress_bar=False, normalize_embeddings=True
            )
            batch_time = time.time() - t0
            all_embeddings.append(np.array(embeddings))

            elapsed = time.time() - encode_start
            done = min(i + batch_size, total)
            if batch_num % 10 == 0 or batch_num == total_batches:
                remaining = (total - done) / (done / elapsed) if done > 0 else 0
                logger.debug("Encoding batch %d/%d (size=%d) in %.2fs, elapsed=%.1fs, ETA=%.1fs",
                              batch_num, total_batches, len(batch), batch_time, elapsed, remaining)

        result = np.vstack(all_embeddings)
        total_time = time.time() - encode_start
        logger.info("Built-in model encode completed: %d texts in %.2fs (%.1f texts/sec)",
                     total, total_time, total / total_time if total_time > 0 else 0)
        return result

    def get_dimension(self):
        self._ensure_loaded()
        return self._model.get_sentence_embedding_dimension()

    @property
    def model_name(self):
        return "bge-large-zh-v1.5 (built-in)"
