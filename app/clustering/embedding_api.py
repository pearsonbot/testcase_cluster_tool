import logging
import time
import numpy as np
import requests
from app.clustering.embedding_base import BaseEmbeddingModel

logger = logging.getLogger(__name__)


class OnlineAPIEmbeddingModel(BaseEmbeddingModel):
    """Calls an OpenAI-compatible embedding API."""

    def __init__(self, api_url, api_key, model_name_str):
        self._api_url = api_url.rstrip("/")
        if self._api_url.endswith("/embeddings"):
            self._api_url = self._api_url[:-len("/embeddings")]
        self._api_key = api_key
        self._model_name_str = model_name_str
        self._dimension = None
        self._total_encoded = 0

    def encode(self, texts, batch_size=32):
        all_embeddings = []
        total = len(texts)
        encode_start = time.time()

        for i in range(0, total, batch_size):
            batch = texts[i:i + batch_size]
            embeddings = self._call_api(batch)
            all_embeddings.extend(embeddings)
            self._total_encoded += len(batch)
            logger.debug("API embedding progress: %d/%d (total encoded: %d)",
                         min(i + batch_size, total), total, self._total_encoded)

        result = np.array(all_embeddings, dtype=np.float32)

        # Normalize to unit vectors
        norms = np.linalg.norm(result, axis=1, keepdims=True)
        result = result / np.maximum(norms, 1e-10)

        if self._dimension is None and result.shape[1] > 0:
            self._dimension = result.shape[1]

        elapsed = time.time() - encode_start
        logger.info("API encode completed: %d texts in %.2fs (%.1f texts/sec)",
                     total, elapsed, total / elapsed if elapsed > 0 else 0)

        return result

    def _call_api(self, texts, max_retries=3):
        """Call embedding API with retry logic."""
        url = f"{self._api_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model_name_str,
            "input": texts,
        }

        preview = texts[0][:50] if texts else ""
        logger.debug("API request: POST %s, batch_size=%d, texts[0]=\"%s...\"",
                      url, len(texts), preview)

        for attempt in range(max_retries):
            try:
                req_start = time.time()
                resp = requests.post(url, headers=headers, json=payload, timeout=120)
                req_time = time.time() - req_start

                if resp.status_code == 429:
                    wait = min(2 ** attempt * 5, 60)
                    logger.warning("API rate limited (429), retry %d/%d, waiting %ds",
                                   attempt + 1, max_retries, wait)
                    time.sleep(wait)
                    continue

                resp.raise_for_status()
                data = resp.json()

                if "data" not in data:
                    raise ValueError(f"Unexpected API response format: {list(data.keys())}")

                items = data["data"]
                items.sort(key=lambda x: x["index"])
                vectors = [item["embedding"] for item in items]

                dim = len(vectors[0]) if vectors else 0
                usage = data.get("usage", {})
                token_info = f", tokens={usage.get('total_tokens', 'N/A')}" if usage else ""

                logger.debug("API response: %d OK, time=%.2fs, vectors=%d, dim=%d%s",
                              resp.status_code, req_time, len(vectors), dim, token_info)

                return vectors

            except requests.exceptions.Timeout:
                logger.warning("API timeout on attempt %d/%d (elapsed=%.1fs)",
                               attempt + 1, max_retries, time.time() - req_start)
                if attempt == max_retries - 1:
                    raise
                time.sleep(2 ** attempt)
            except requests.exceptions.ConnectionError as e:
                logger.error("API connection error: %s", e)
                raise ConnectionError(f"Cannot connect to API at {url}: {e}")

        raise RuntimeError("Max retries exceeded for API call")

    def get_dimension(self):
        if self._dimension is None:
            result = self.encode(["test"])
            self._dimension = result.shape[1]
        return self._dimension

    @property
    def model_name(self):
        return f"Online API ({self._model_name_str})"
