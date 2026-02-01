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
        # Strip /embeddings suffix if user included it
        if self._api_url.endswith("/embeddings"):
            self._api_url = self._api_url[:-len("/embeddings")]
        self._api_key = api_key
        self._model_name_str = model_name_str
        self._dimension = None

    def encode(self, texts, batch_size=32):
        all_embeddings = []
        total = len(texts)

        for i in range(0, total, batch_size):
            batch = texts[i:i + batch_size]
            embeddings = self._call_api(batch)
            all_embeddings.extend(embeddings)
            logger.debug("API embedding progress: %d/%d", min(i + batch_size, total), total)

        result = np.array(all_embeddings, dtype=np.float32)

        # Normalize to unit vectors
        norms = np.linalg.norm(result, axis=1, keepdims=True)
        result = result / np.maximum(norms, 1e-10)

        if self._dimension is None and result.shape[1] > 0:
            self._dimension = result.shape[1]

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

        for attempt in range(max_retries):
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=120)

                if resp.status_code == 429:
                    wait = min(2 ** attempt * 5, 60)
                    logger.warning("Rate limited, waiting %d seconds...", wait)
                    time.sleep(wait)
                    continue

                resp.raise_for_status()
                data = resp.json()

                if "data" not in data:
                    raise ValueError(f"Unexpected API response format: {list(data.keys())}")

                items = data["data"]
                items.sort(key=lambda x: x["index"])
                return [item["embedding"] for item in items]

            except requests.exceptions.Timeout:
                logger.warning("API timeout on attempt %d/%d", attempt + 1, max_retries)
                if attempt == max_retries - 1:
                    raise
                time.sleep(2 ** attempt)
            except requests.exceptions.ConnectionError as e:
                raise ConnectionError(f"Cannot connect to API at {url}: {e}")

        raise RuntimeError("Max retries exceeded for API call")

    def get_dimension(self):
        if self._dimension is None:
            # Probe with a test sentence
            result = self.encode(["test"])
            self._dimension = result.shape[1]
        return self._dimension

    @property
    def model_name(self):
        return f"Online API ({self._model_name_str})"
