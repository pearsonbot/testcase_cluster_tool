import json
import logging
import threading
import time
from datetime import datetime
from collections import Counter

from flask import Blueprint, request, jsonify, current_app
from app.database import get_db

logger = logging.getLogger(__name__)

bp = Blueprint('cluster_api', __name__, url_prefix='/api/cluster')

# Module-level state for background clustering task
_task_state = {
    "status": "idle",  # idle | running | completed | error
    "progress": "",
    "phase": None,
    "phase_name": "",
    "phase_index": 0,
    "total_phases": 5,
    "phase_progress": 0,
    "overall_progress": 0,
    "detail": "",
    "elapsed_seconds": 0,
    "start_time": None,
    "result": None,
    "error": None,
}
_task_lock = threading.Lock()


def _update_progress(phase, phase_name, phase_index, phase_progress, overall_progress, detail):
    """Callback for cluster engine to update progress."""
    with _task_lock:
        _task_state["phase"] = phase
        _task_state["phase_name"] = phase_name
        _task_state["phase_index"] = phase_index
        _task_state["phase_progress"] = phase_progress
        _task_state["overall_progress"] = overall_progress
        _task_state["detail"] = detail
        if _task_state["start_time"]:
            _task_state["elapsed_seconds"] = time.time() - _task_state["start_time"]


def _run_clustering(app_config, db_path, similarity_threshold):
    """Run clustering in background thread."""
    import sqlite3
    import numpy as np

    global _task_state

    try:
        with _task_lock:
            _task_state["status"] = "running"
            _task_state["progress"] = "加载步骤数据..."
            _task_state["start_time"] = time.time()
            _task_state["error"] = None
            _task_state["overall_progress"] = 0

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            "SELECT id, operation FROM test_steps ORDER BY id"
        ).fetchall()

        if not rows:
            with _task_lock:
                _task_state["status"] = "error"
                _task_state["error"] = "未找到测试步骤，请先导入数据。"
            conn.close()
            return

        step_ids = [r['id'] for r in rows]
        step_texts = [r['operation'] for r in rows]

        # Load model
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

        # Run clustering with progress callback
        from app.clustering.cluster_engine import ClusterEngine
        engine = ClusterEngine()
        result = engine.run(
            step_ids, step_texts,
            similarity_threshold=similarity_threshold,
            model=model,
            progress_callback=_update_progress
        )

        labels = result["labels"]
        cluster_labels = result["cluster_labels"]

        # Phase 5 continued: Save to database
        _update_progress("saving", "结果保存", 5, 60, 96, "保存聚类结果...")

        # Create history record
        run_time = datetime.now().isoformat()
        model_type = settings.get("model_type", "builtin")
        model_name = model.model_name
        elapsed = time.time() - _task_state["start_time"]

        # Clear is_current on all history records
        conn.execute("UPDATE cluster_history SET is_current = 0")

        cursor = conn.execute(
            "INSERT INTO cluster_history (run_time, model_type, model_name, similarity_threshold, "
            "total_steps, total_clusters, noise_count, elapsed_seconds, is_current) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)",
            (run_time, model_type, model_name, similarity_threshold,
             len(step_ids), result["total_clusters"], result["noise_count"], elapsed)
        )
        history_id = cursor.lastrowid

        _update_progress("saving", "结果保存", 5, 70, 97, "保存聚类结果到数据库...")

        # Delete old current results (without history_id or with old current flag)
        conn.execute("DELETE FROM cluster_results WHERE history_id IS NULL")
        conn.execute("DELETE FROM cluster_info WHERE history_id IS NULL")

        # Save results with history_id
        for i, step_id in enumerate(step_ids):
            cid = int(labels[i])
            clabel = cluster_labels.get(cid, "")
            conn.execute(
                "INSERT INTO cluster_results (step_id, cluster_id, cluster_label, similarity_threshold, history_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (int(step_id), cid, clabel, similarity_threshold, history_id)
            )

        _update_progress("saving", "结果保存", 5, 90, 99, "保存簇信息...")

        # Compute and save cluster info
        unique_labels = set(int(l) for l in labels)
        unique_labels.discard(-1)
        label_counts = Counter(int(l) for l in labels)

        for cid in unique_labels:
            step_count = label_counts[cid]
            case_ids_in_cluster = conn.execute(
                "SELECT DISTINCT ts.case_id FROM cluster_results cr "
                "JOIN test_steps ts ON cr.step_id = ts.id "
                "WHERE cr.cluster_id = ? AND cr.history_id = ?",
                (cid, history_id)
            ).fetchall()
            case_count = len(case_ids_in_cluster)

            conn.execute(
                "INSERT INTO cluster_info (cluster_id, label, step_count, case_count, threshold, history_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (cid, cluster_labels.get(cid, ""), step_count, case_count, similarity_threshold, history_id)
            )

        conn.commit()
        conn.close()

        noise_count = int((labels == -1).sum())
        total_clusters = len(unique_labels)

        with _task_lock:
            _task_state["status"] = "completed"
            _task_state["progress"] = ""
            _task_state["overall_progress"] = 100
            _task_state["detail"] = ""
            _task_state["result"] = {
                "total_clusters": total_clusters,
                "noise_count": noise_count,
                "total_steps": len(step_ids),
                "threshold": similarity_threshold,
                "history_id": history_id,
            }
            _task_state["elapsed_seconds"] = elapsed

        logger.info("Clustering completed: %d clusters, %d noise steps, threshold=%.2f, elapsed=%.1fs",
                     total_clusters, noise_count, similarity_threshold, elapsed)

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
            return jsonify({"success": False, "error": "聚类正在执行中，请勿重复操作"}), 409

    data = request.get_json() or {}
    threshold = float(data.get('similarity_threshold', 0.80))

    if threshold < 0.5 or threshold > 0.95:
        return jsonify({"success": False, "error": "阈值必须在 0.5 到 0.95 之间"}), 400

    app_config = {
        'BUILTIN_MODEL_PATH': current_app.config['BUILTIN_MODEL_PATH'],
        'DATABASE_PATH': current_app.config['DATABASE_PATH'],
    }
    db_path = current_app.config['DATABASE_PATH']

    with _task_lock:
        _task_state["status"] = "running"
        _task_state["progress"] = "启动中..."
        _task_state["phase"] = None
        _task_state["phase_name"] = ""
        _task_state["phase_index"] = 0
        _task_state["phase_progress"] = 0
        _task_state["overall_progress"] = 0
        _task_state["detail"] = ""
        _task_state["elapsed_seconds"] = 0
        _task_state["start_time"] = time.time()
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
            "phase": _task_state["phase"],
            "phase_name": _task_state["phase_name"],
            "phase_index": _task_state["phase_index"],
            "total_phases": _task_state["total_phases"],
            "phase_progress": _task_state["phase_progress"],
            "overall_progress": _task_state["overall_progress"],
            "detail": _task_state["detail"],
            "elapsed_seconds": round(_task_state.get("elapsed_seconds", 0), 1),
            "result": _task_state["result"],
            "error": _task_state["error"],
        })


@bp.route('/list', methods=['GET'])
def cluster_list():
    """Return all clusters for current active history."""
    db = get_db()
    history_id = request.args.get('history_id')

    if history_id:
        rows = db.execute(
            "SELECT cluster_id, label, step_count, case_count, threshold "
            "FROM cluster_info WHERE history_id = ? ORDER BY step_count DESC",
            (history_id,)
        ).fetchall()
    else:
        # Get current active history
        current = db.execute(
            "SELECT id FROM cluster_history WHERE is_current = 1 ORDER BY id DESC LIMIT 1"
        ).fetchone()

        if current:
            rows = db.execute(
                "SELECT cluster_id, label, step_count, case_count, threshold "
                "FROM cluster_info WHERE history_id = ? ORDER BY step_count DESC",
                (current['id'],)
            ).fetchall()
        else:
            # Fallback: get any cluster_info
            rows = db.execute(
                "SELECT cluster_id, label, step_count, case_count, threshold "
                "FROM cluster_info ORDER BY step_count DESC"
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
    history_id = request.args.get('history_id')

    if history_id:
        info = db.execute(
            "SELECT * FROM cluster_info WHERE cluster_id = ? AND history_id = ?",
            (cluster_id, history_id)
        ).fetchone()
    else:
        current = db.execute(
            "SELECT id FROM cluster_history WHERE is_current = 1 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        hid = current['id'] if current else None

        if hid:
            info = db.execute(
                "SELECT * FROM cluster_info WHERE cluster_id = ? AND history_id = ?",
                (cluster_id, hid)
            ).fetchone()
        else:
            info = db.execute(
                "SELECT * FROM cluster_info WHERE cluster_id = ? LIMIT 1",
                (cluster_id,)
            ).fetchone()

    if not info:
        return jsonify({"success": False, "error": "簇未找到"}), 404

    hid_filter = info['history_id'] if info['history_id'] else None
    if hid_filter:
        rows = db.execute(
            "SELECT ts.id, ts.operation, ts.step_no, ts.case_id, tc.title as case_title "
            "FROM cluster_results cr "
            "JOIN test_steps ts ON cr.step_id = ts.id "
            "JOIN test_cases tc ON ts.case_id = tc.id "
            "WHERE cr.cluster_id = ? AND cr.history_id = ? "
            "ORDER BY ts.case_id, ts.step_no",
            (cluster_id, hid_filter)
        ).fetchall()
    else:
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


# ---- History endpoints ----

@bp.route('/history', methods=['GET'])
def cluster_history_list():
    """Return all clustering history records."""
    db = get_db()
    rows = db.execute(
        "SELECT * FROM cluster_history ORDER BY id DESC"
    ).fetchall()

    records = [
        {
            "id": r['id'],
            "run_time": r['run_time'],
            "model_type": r['model_type'],
            "model_name": r['model_name'],
            "similarity_threshold": r['similarity_threshold'],
            "total_steps": r['total_steps'],
            "total_clusters": r['total_clusters'],
            "noise_count": r['noise_count'],
            "elapsed_seconds": r['elapsed_seconds'],
            "is_current": bool(r['is_current']),
        }
        for r in rows
    ]

    return jsonify({"success": True, "records": records})


@bp.route('/history/<int:history_id>', methods=['GET'])
def cluster_history_detail(history_id):
    """Return a specific history record with its clusters."""
    db = get_db()
    record = db.execute("SELECT * FROM cluster_history WHERE id = ?", (history_id,)).fetchone()
    if not record:
        return jsonify({"success": False, "error": "历史记录未找到"}), 404

    clusters = db.execute(
        "SELECT cluster_id, label, step_count, case_count "
        "FROM cluster_info WHERE history_id = ? ORDER BY step_count DESC",
        (history_id,)
    ).fetchall()

    return jsonify({
        "success": True,
        "record": {
            "id": record['id'],
            "run_time": record['run_time'],
            "model_type": record['model_type'],
            "model_name": record['model_name'],
            "similarity_threshold": record['similarity_threshold'],
            "total_steps": record['total_steps'],
            "total_clusters": record['total_clusters'],
            "noise_count": record['noise_count'],
            "elapsed_seconds": record['elapsed_seconds'],
            "is_current": bool(record['is_current']),
        },
        "clusters": [dict(c) for c in clusters],
    })


@bp.route('/history/<int:history_id>', methods=['DELETE'])
def delete_history(history_id):
    """Delete a history record and its associated data."""
    db = get_db()
    record = db.execute("SELECT * FROM cluster_history WHERE id = ?", (history_id,)).fetchone()
    if not record:
        return jsonify({"success": False, "error": "历史记录未找到"}), 404

    db.execute("DELETE FROM cluster_results WHERE history_id = ?", (history_id,))
    db.execute("DELETE FROM cluster_info WHERE history_id = ?", (history_id,))
    db.execute("DELETE FROM cluster_history WHERE id = ?", (history_id,))
    db.commit()

    logger.info("Deleted cluster history record #%d", history_id)
    return jsonify({"success": True})


@bp.route('/history/<int:history_id>/activate', methods=['POST'])
def activate_history(history_id):
    """Set a history record as the current active result."""
    db = get_db()
    record = db.execute("SELECT * FROM cluster_history WHERE id = ?", (history_id,)).fetchone()
    if not record:
        return jsonify({"success": False, "error": "历史记录未找到"}), 404

    db.execute("UPDATE cluster_history SET is_current = 0")
    db.execute("UPDATE cluster_history SET is_current = 1 WHERE id = ?", (history_id,))
    db.commit()

    logger.info("Activated cluster history record #%d", history_id)
    return jsonify({"success": True})


@bp.route('/history/compare', methods=['GET'])
def compare_history():
    """Compare two history records side by side."""
    id1 = request.args.get('id1', type=int)
    id2 = request.args.get('id2', type=int)

    if not id1 or not id2:
        return jsonify({"success": False, "error": "请提供两条历史记录的ID (id1, id2)"}), 400
    if id1 == id2:
        return jsonify({"success": False, "error": "请选择两条不同的历史记录"}), 400

    db = get_db()

    rec1 = db.execute("SELECT * FROM cluster_history WHERE id = ?", (id1,)).fetchone()
    rec2 = db.execute("SELECT * FROM cluster_history WHERE id = ?", (id2,)).fetchone()

    if not rec1 or not rec2:
        return jsonify({"success": False, "error": "历史记录未找到"}), 404

    # Get clusters for each history
    clusters1 = db.execute(
        "SELECT cluster_id, label, step_count, case_count FROM cluster_info WHERE history_id = ? ORDER BY step_count DESC",
        (id1,)
    ).fetchall()
    clusters2 = db.execute(
        "SELECT cluster_id, label, step_count, case_count FROM cluster_info WHERE history_id = ? ORDER BY step_count DESC",
        (id2,)
    ).fetchall()

    labels1 = {r['label'] for r in clusters1 if r['label']}
    labels2 = {r['label'] for r in clusters2 if r['label']}

    new_labels = sorted(labels2 - labels1)
    disappeared_labels = sorted(labels1 - labels2)
    common_labels = sorted(labels1 & labels2)

    def record_summary(rec):
        return {
            "id": rec['id'],
            "run_time": rec['run_time'],
            "model_type": rec['model_type'],
            "model_name": rec['model_name'],
            "similarity_threshold": rec['similarity_threshold'],
            "total_steps": rec['total_steps'],
            "total_clusters": rec['total_clusters'],
            "noise_count": rec['noise_count'],
            "elapsed_seconds": rec['elapsed_seconds'],
        }

    return jsonify({
        "success": True,
        "record1": record_summary(rec1),
        "record2": record_summary(rec2),
        "clusters1": [dict(c) for c in clusters1],
        "clusters2": [dict(c) for c in clusters2],
        "new_labels": new_labels,
        "disappeared_labels": disappeared_labels,
        "common_labels": common_labels,
    })


@bp.route('/current-summary', methods=['GET'])
def current_summary():
    """Return summary of the current active clustering result for the main page panel."""
    db = get_db()

    current = db.execute(
        "SELECT * FROM cluster_history WHERE is_current = 1 ORDER BY id DESC LIMIT 1"
    ).fetchone()

    if not current:
        return jsonify({"success": True, "summary": None, "top_clusters": []})

    # Get top 10 clusters by step count
    top_clusters = db.execute(
        "SELECT cluster_id, label, step_count, case_count "
        "FROM cluster_info WHERE history_id = ? ORDER BY step_count DESC LIMIT 10",
        (current['id'],)
    ).fetchall()

    return jsonify({
        "success": True,
        "summary": {
            "history_id": current['id'],
            "run_time": current['run_time'],
            "model_type": current['model_type'],
            "model_name": current['model_name'],
            "similarity_threshold": current['similarity_threshold'],
            "total_steps": current['total_steps'],
            "total_clusters": current['total_clusters'],
            "noise_count": current['noise_count'],
            "elapsed_seconds": current['elapsed_seconds'],
        },
        "top_clusters": [dict(c) for c in top_clusters],
    })
