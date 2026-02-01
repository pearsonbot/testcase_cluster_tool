import json
import logging
import threading

from flask import Blueprint, request, jsonify, current_app
from app.database import get_db

logger = logging.getLogger(__name__)

bp = Blueprint('cluster_api', __name__, url_prefix='/api/cluster')

# Module-level state for background clustering task
_task_state = {
    "status": "idle",  # idle | running | completed | error
    "progress": "",
    "result": None,
    "error": None,
}
_task_lock = threading.Lock()


def _run_clustering(app_config, db_path, similarity_threshold):
    """Run clustering in background thread."""
    import sqlite3
    import numpy as np

    global _task_state

    try:
        with _task_lock:
            _task_state["status"] = "running"
            _task_state["progress"] = "Loading steps from database..."
            _task_state["error"] = None

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            "SELECT id, operation FROM test_steps ORDER BY id"
        ).fetchall()

        if not rows:
            with _task_lock:
                _task_state["status"] = "error"
                _task_state["error"] = "No test steps found. Please import data first."
            conn.close()
            return

        step_ids = [r['id'] for r in rows]
        step_texts = [r['operation'] for r in rows]

        with _task_lock:
            _task_state["progress"] = f"Preprocessing {len(step_texts)} steps..."

        from app.clustering.preprocessor import preprocess
        cleaned = [preprocess(t) for t in step_texts]

        with _task_lock:
            _task_state["progress"] = f"Loading embedding model..."

        from app.clustering.model_manager import ModelManager
        settings = {}
        for row in conn.execute("SELECT key, value FROM settings").fetchall():
            settings[row['key']] = row['value']

        model_config = {
            "model_type": settings.get("model_type", "builtin"),
            "model_path": settings.get("model_path", ""),
            "api_url": settings.get("api_url", ""),
            "api_key": settings.get("api_key", ""),
            "api_model_name": settings.get("api_model_name", ""),
            "builtin_model_path": app_config['BUILTIN_MODEL_PATH'],
        }
        model = ModelManager.get_model(model_config)

        with _task_lock:
            _task_state["progress"] = f"Computing embeddings for {len(cleaned)} steps..."

        embeddings = model.encode(cleaned, batch_size=64)

        with _task_lock:
            _task_state["progress"] = "Computing cosine distance matrix..."

        similarity_matrix = np.dot(embeddings, embeddings.T)
        distance_matrix = 1 - similarity_matrix
        distance_matrix = np.clip(distance_matrix, 0, 2)

        with _task_lock:
            _task_state["progress"] = "Running DBSCAN clustering..."

        from sklearn.cluster import DBSCAN
        eps = 1 - similarity_threshold
        clustering = DBSCAN(eps=eps, min_samples=2, metric='precomputed')
        labels = clustering.fit_predict(distance_matrix)

        with _task_lock:
            _task_state["progress"] = "Extracting cluster labels..."

        # Extract labels
        unique_labels = set(labels)
        unique_labels.discard(-1)
        cluster_labels = {}

        for cid in unique_labels:
            mask = labels == cid
            cluster_embeddings = embeddings[mask]
            cluster_texts = [cleaned[i] for i in range(len(cleaned)) if labels[i] == cid]
            centroid = cluster_embeddings.mean(axis=0)
            centroid_norm = centroid / (np.linalg.norm(centroid) + 1e-10)
            similarities = np.dot(cluster_embeddings, centroid_norm)
            best_idx = np.argmax(similarities)
            cluster_labels[int(cid)] = cluster_texts[best_idx]

        with _task_lock:
            _task_state["progress"] = "Saving results to database..."

        # Save results
        conn.execute("DELETE FROM cluster_results")
        conn.execute("DELETE FROM cluster_info")

        for i, step_id in enumerate(step_ids):
            cid = int(labels[i])
            clabel = cluster_labels.get(cid, "")
            conn.execute(
                "INSERT INTO cluster_results (step_id, cluster_id, cluster_label, similarity_threshold) "
                "VALUES (?, ?, ?, ?)",
                (step_id, cid, clabel, similarity_threshold)
            )

        # Compute cluster info
        from collections import Counter
        label_counts = Counter(labels)
        for cid in unique_labels:
            cid_int = int(cid)
            step_count = label_counts[cid]
            # Count distinct cases
            case_ids_in_cluster = conn.execute(
                "SELECT DISTINCT ts.case_id FROM cluster_results cr "
                "JOIN test_steps ts ON cr.step_id = ts.id "
                "WHERE cr.cluster_id = ?",
                (cid_int,)
            ).fetchall()
            case_count = len(case_ids_in_cluster)

            conn.execute(
                "INSERT INTO cluster_info (cluster_id, label, step_count, case_count, threshold) "
                "VALUES (?, ?, ?, ?, ?)",
                (cid_int, cluster_labels.get(cid_int, ""), step_count, case_count, similarity_threshold)
            )

        conn.commit()
        conn.close()

        noise_count = int((labels == -1).sum())
        total_clusters = len(unique_labels)

        with _task_lock:
            _task_state["status"] = "completed"
            _task_state["progress"] = ""
            _task_state["result"] = {
                "total_clusters": total_clusters,
                "noise_count": noise_count,
                "total_steps": len(step_ids),
                "threshold": similarity_threshold,
            }

        logger.info("Clustering completed: %d clusters, %d noise steps, threshold=%.2f",
                     total_clusters, noise_count, similarity_threshold)

    except Exception as e:
        logger.error("Clustering failed: %s", e, exc_info=True)
        with _task_lock:
            _task_state["status"] = "error"
            _task_state["error"] = str(e)


@bp.route('/run', methods=['POST'])
def run_clustering():
    """Trigger clustering in background thread."""
    with _task_lock:
        if _task_state["status"] == "running":
            return jsonify({"success": False, "error": "Clustering is already running"}), 409

    data = request.get_json() or {}
    threshold = float(data.get('similarity_threshold', 0.80))

    if threshold < 0.5 or threshold > 0.95:
        return jsonify({"success": False, "error": "Threshold must be between 0.5 and 0.95"}), 400

    app_config = {
        'BUILTIN_MODEL_PATH': current_app.config['BUILTIN_MODEL_PATH'],
        'DATABASE_PATH': current_app.config['DATABASE_PATH'],
    }
    db_path = current_app.config['DATABASE_PATH']

    with _task_lock:
        _task_state["status"] = "running"
        _task_state["progress"] = "Starting..."
        _task_state["result"] = None
        _task_state["error"] = None

    t = threading.Thread(
        target=_run_clustering,
        args=(app_config, db_path, threshold),
        daemon=True
    )
    t.start()

    logger.info("Clustering started with threshold=%.2f", threshold)
    return jsonify({"success": True, "status": "started"})


@bp.route('/status', methods=['GET'])
def cluster_status():
    """Return clustering progress/result."""
    with _task_lock:
        return jsonify({
            "success": True,
            "status": _task_state["status"],
            "progress": _task_state["progress"],
            "result": _task_state["result"],
            "error": _task_state["error"],
        })


@bp.route('/list', methods=['GET'])
def cluster_list():
    """Return all clusters."""
    db = get_db()
    rows = db.execute(
        "SELECT cluster_id, label, step_count, case_count, threshold "
        "FROM cluster_info ORDER BY cluster_id"
    ).fetchall()

    clusters = [
        {
            "cluster_id": r['cluster_id'],
            "label": r['label'],
            "step_count": r['step_count'],
            "case_count": r['case_count'],
        }
        for r in rows
    ]

    return jsonify({"success": True, "clusters": clusters})


@bp.route('/<int:cluster_id>', methods=['GET'])
def cluster_detail(cluster_id):
    """Return steps in a cluster."""
    db = get_db()

    info = db.execute(
        "SELECT * FROM cluster_info WHERE cluster_id = ?", (cluster_id,)
    ).fetchone()
    if not info:
        return jsonify({"success": False, "error": "Cluster not found"}), 404

    rows = db.execute(
        "SELECT ts.id, ts.operation, ts.step_no, ts.case_id, tc.title as case_title "
        "FROM cluster_results cr "
        "JOIN test_steps ts ON cr.step_id = ts.id "
        "JOIN test_cases tc ON ts.case_id = tc.id "
        "WHERE cr.cluster_id = ? "
        "ORDER BY ts.case_id, ts.step_no",
        (cluster_id,)
    ).fetchall()

    steps = [
        {
            "step_id": r['id'],
            "operation": r['operation'],
            "step_no": r['step_no'],
            "case_id": r['case_id'],
            "case_title": r['case_title'],
        }
        for r in rows
    ]

    return jsonify({
        "success": True,
        "cluster": {
            "cluster_id": info['cluster_id'],
            "label": info['label'],
            "step_count": info['step_count'],
            "case_count": info['case_count'],
        },
        "steps": steps,
    })
