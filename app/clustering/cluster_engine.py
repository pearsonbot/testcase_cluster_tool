import logging
import numpy as np

logger = logging.getLogger(__name__)


class ClusterEngine:
    """DBSCAN clustering engine for test steps."""

    def run(self, step_ids, step_texts, similarity_threshold=0.80, model=None, progress_callback=None):
        """Execute the full clustering pipeline.

        Args:
            step_ids: list of step database IDs
            step_texts: list of step operation texts
            similarity_threshold: cosine similarity threshold (0.5 - 0.95)
            model: BaseEmbeddingModel instance
            progress_callback: optional callback(phase, detail)

        Returns:
            dict with clustering results
        """
        from app.clustering.preprocessor import preprocess

        if not step_texts:
            return {
                "labels": np.array([]),
                "cluster_labels": {},
                "total_clusters": 0,
                "noise_count": 0,
            }

        # Step 1: Preprocess
        if progress_callback:
            progress_callback("preprocessing", len(step_texts))
        cleaned = [preprocess(t) for t in step_texts]

        # Step 2: Embed
        if progress_callback:
            progress_callback("embedding", len(cleaned))
        embeddings = model.encode(cleaned, batch_size=64)

        # Step 3: Cosine distance matrix
        if progress_callback:
            progress_callback("distance_matrix", len(cleaned))
        # Since embeddings are normalized, cosine_similarity = dot product
        similarity_matrix = np.dot(embeddings, embeddings.T)
        distance_matrix = 1 - similarity_matrix
        distance_matrix = np.clip(distance_matrix, 0, 2)

        # Step 4: DBSCAN
        if progress_callback:
            progress_callback("dbscan", len(cleaned))
        eps = 1 - similarity_threshold
        from sklearn.cluster import DBSCAN
        clustering = DBSCAN(eps=eps, min_samples=2, metric='precomputed')
        labels = clustering.fit_predict(distance_matrix)

        # Step 5: Extract cluster labels
        if progress_callback:
            progress_callback("labels", 0)
        cluster_labels = self._extract_labels(labels, embeddings, cleaned)

        unique_labels = set(labels)
        unique_labels.discard(-1)
        noise_count = int((labels == -1).sum())

        logger.info(
            "Clustering done: %d clusters, %d noise steps (threshold=%.2f)",
            len(unique_labels), noise_count, similarity_threshold
        )

        return {
            "labels": labels,
            "cluster_labels": cluster_labels,
            "total_clusters": len(unique_labels),
            "noise_count": noise_count,
        }

    def _extract_labels(self, labels, embeddings, texts):
        """Extract representative text for each cluster.

        For each cluster: compute centroid, find nearest member, use its text.
        """
        unique_labels = set(labels)
        unique_labels.discard(-1)
        cluster_labels = {}

        for cid in unique_labels:
            cid_int = int(cid)
            mask = labels == cid
            cluster_embeddings = embeddings[mask]
            cluster_texts = [texts[i] for i in range(len(texts)) if labels[i] == cid]

            if not cluster_texts:
                continue

            centroid = cluster_embeddings.mean(axis=0)
            centroid_norm = centroid / (np.linalg.norm(centroid) + 1e-10)
            similarities = np.dot(cluster_embeddings, centroid_norm)
            best_idx = int(np.argmax(similarities))
            cluster_labels[cid_int] = cluster_texts[best_idx]

        return cluster_labels
