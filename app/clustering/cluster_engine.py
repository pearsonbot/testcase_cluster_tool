import logging
import time
import numpy as np
from collections import Counter

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
            progress_callback: optional callback(phase, phase_name, phase_index, phase_progress, overall_progress, detail)

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

        total = len(step_texts)

        # Phase 1: Preprocess (0-10%)
        if progress_callback:
            progress_callback("preprocessing", "文本预处理", 1, 0, 2, f"预处理 {total} 条步骤...")

        t0 = time.time()
        cleaned = [preprocess(t) for t in step_texts]
        preprocess_time = time.time() - t0
        logger.info("Text preprocessing completed: %d steps in %.2fs", total, preprocess_time)

        if progress_callback:
            progress_callback("preprocessing", "文本预处理", 1, 100, 10, f"预处理完成 ({total} 条)")

        # Phase 2: Model loading (10-20%)
        if progress_callback:
            progress_callback("model_loading", "模型加载", 2, 0, 12, "加载嵌入模型...")

        t0 = time.time()
        # Trigger model loading (lazy load)
        _ = model.model_name
        load_time = time.time() - t0
        logger.info("Embedding model ready: %s (%.2fs)", model.model_name, load_time)

        if progress_callback:
            progress_callback("model_loading", "模型加载", 2, 100, 20, f"模型已就绪: {model.model_name}")

        # Phase 3: Embedding (20-70%)
        if progress_callback:
            progress_callback("embedding", "向量计算", 3, 0, 20, f"向量计算: 0/{total}")

        batch_size = 64
        all_embeddings = []
        t0 = time.time()

        for i in range(0, total, batch_size):
            batch = cleaned[i:i + batch_size]
            batch_t = time.time()
            batch_emb = model.encode(batch, batch_size=batch_size)
            batch_time = time.time() - batch_t

            all_embeddings.append(batch_emb)
            done = min(i + batch_size, total)
            phase_pct = int(done / total * 100)
            overall_pct = 20 + int(done / total * 50)

            logger.debug("Encoding batch %d/%d (size=%d) in %.2fs, progress: %d/%d",
                         i // batch_size + 1,
                         (total + batch_size - 1) // batch_size,
                         len(batch), batch_time, done, total)

            if progress_callback:
                progress_callback("embedding", "向量计算", 3, phase_pct, overall_pct,
                                  f"向量计算: {done}/{total} ({phase_pct}%)")

        embeddings = np.vstack(all_embeddings)
        embed_time = time.time() - t0
        logger.info("Embedding completed: %d texts in %.2fs (%.1f texts/sec)",
                     total, embed_time, total / embed_time if embed_time > 0 else 0)

        # Phase 4: Clustering (70-90%)
        if progress_callback:
            progress_callback("clustering", "聚类计算", 4, 0, 70, "计算余弦距离矩阵...")

        t0 = time.time()
        logger.info("Computing cosine distance matrix (%dx%d)...", total, total)
        similarity_matrix = np.dot(embeddings, embeddings.T)
        distance_matrix = 1 - similarity_matrix
        distance_matrix = np.clip(distance_matrix, 0, 2)
        dist_time = time.time() - t0
        logger.info("Distance matrix computed in %.2fs", dist_time)

        if progress_callback:
            progress_callback("clustering", "聚类计算", 4, 50, 80, "运行 DBSCAN...")

        eps = 1 - similarity_threshold
        logger.info("Running DBSCAN: eps=%.4f, min_samples=2", eps)

        t0 = time.time()
        from sklearn.cluster import DBSCAN
        clustering = DBSCAN(eps=eps, min_samples=2, metric='precomputed')
        labels = clustering.fit_predict(distance_matrix)
        dbscan_time = time.time() - t0
        logger.info("DBSCAN completed in %.2fs", dbscan_time)

        unique_labels = set(labels)
        unique_labels.discard(-1)
        noise_count = int((labels == -1).sum())
        total_clusters = len(unique_labels)

        # Log cluster distribution
        label_counts = Counter(int(l) for l in labels if l >= 0)
        if label_counts:
            sizes = list(label_counts.values())
            logger.info("Results: %d clusters, %d noise steps", total_clusters, noise_count)
            logger.info("Cluster size distribution: min=%d, max=%d, median=%d, mean=%.1f",
                         min(sizes), max(sizes),
                         sorted(sizes)[len(sizes) // 2],
                         sum(sizes) / len(sizes))

        if progress_callback:
            progress_callback("clustering", "聚类计算", 4, 100, 90,
                              f"聚类完成: {total_clusters} 个簇, {noise_count} 个噪声步骤")

        # Phase 5: Extract labels and save (90-100%)
        if progress_callback:
            progress_callback("saving", "结果保存", 5, 0, 90, "提取簇标签...")

        cluster_labels = self._extract_labels(labels, embeddings, cleaned)

        if progress_callback:
            progress_callback("saving", "结果保存", 5, 50, 95, "保存结果到数据库...")

        logger.info(
            "Clustering done: %d clusters, %d noise steps (threshold=%.2f)",
            total_clusters, noise_count, similarity_threshold
        )

        return {
            "labels": labels,
            "cluster_labels": cluster_labels,
            "total_clusters": total_clusters,
            "noise_count": noise_count,
        }

    def _extract_labels(self, labels, embeddings, texts):
        """Extract representative text for each cluster."""
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
