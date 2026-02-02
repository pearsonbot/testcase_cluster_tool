import json
import logging

from flask import Blueprint, request, jsonify
from app.database import get_db

logger = logging.getLogger(__name__)

bp = Blueprint('query_api', __name__, url_prefix='/api/cases')


@bp.route('/search', methods=['GET'])
def search_cases():
    """Search cases by ID or title."""
    q = request.args.get('q', '').strip()
    mode = request.args.get('mode', 'title')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))

    if not q:
        return jsonify({"success": True, "cases": [], "total": 0})

    db = get_db()
    offset = (page - 1) * per_page

    if mode == 'id':
        rows = db.execute(
            "SELECT tc.*, (SELECT COUNT(*) FROM test_steps WHERE case_id = tc.id) as step_count "
            "FROM test_cases tc WHERE tc.id = ?",
            (q,)
        ).fetchall()
        total = len(rows)
    else:
        count_row = db.execute(
            "SELECT COUNT(*) as cnt FROM test_cases WHERE title LIKE ?",
            (f"%{q}%",)
        ).fetchone()
        total = count_row['cnt']
        rows = db.execute(
            "SELECT tc.*, (SELECT COUNT(*) FROM test_steps WHERE case_id = tc.id) as step_count "
            "FROM test_cases tc WHERE tc.title LIKE ? ORDER BY tc.id LIMIT ? OFFSET ?",
            (f"%{q}%", per_page, offset)
        ).fetchall()

    cases = []
    for row in rows:
        extra = {}
        if row['extra_fields']:
            try:
                extra = json.loads(row['extra_fields'])
            except (json.JSONDecodeError, TypeError):
                pass
        cases.append({
            "id": row['id'],
            "title": row['title'],
            "extra_fields": extra,
            "source_file": row['source_file'],
            "step_count": row['step_count'],
        })

    return jsonify({
        "success": True,
        "cases": cases,
        "total": total,
        "page": page,
        "per_page": per_page,
    })


@bp.route('/browse', methods=['GET'])
def browse_cases():
    """Browse all cases with pagination, sorting, and filtering."""
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    sort = request.args.get('sort', 'id')
    order = request.args.get('order', 'asc')
    source = request.args.get('source', '').strip()
    keyword = request.args.get('keyword', '').strip()

    db = get_db()
    offset = (page - 1) * per_page

    # Validate sort column
    allowed_sorts = {'id': 'tc.id', 'title': 'tc.title', 'step_count': 'step_count',
                     'source_file': 'tc.source_file', 'import_time': 'tc.import_time'}
    sort_col = allowed_sorts.get(sort, 'tc.id')
    order_dir = 'DESC' if order.lower() == 'desc' else 'ASC'

    # Build WHERE clause
    conditions = []
    params = []
    if source:
        conditions.append("tc.source_file = ?")
        params.append(source)
    if keyword:
        conditions.append("tc.title LIKE ?")
        params.append(f"%{keyword}%")

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    # Count total
    count_sql = f"SELECT COUNT(*) as cnt FROM test_cases tc {where_clause}"
    total = db.execute(count_sql, params).fetchone()['cnt']

    # Query data
    query_sql = f"""
        SELECT tc.*, (SELECT COUNT(*) FROM test_steps WHERE case_id = tc.id) as step_count
        FROM test_cases tc
        {where_clause}
        ORDER BY {sort_col} {order_dir}
        LIMIT ? OFFSET ?
    """
    query_params = params + [per_page, offset]
    rows = db.execute(query_sql, query_params).fetchall()

    cases = []
    for row in rows:
        cases.append({
            "id": row['id'],
            "title": row['title'],
            "source_file": row['source_file'],
            "import_time": row['import_time'],
            "step_count": row['step_count'],
        })

    return jsonify({
        "success": True,
        "cases": cases,
        "total": total,
        "page": page,
        "per_page": per_page,
    })


@bp.route('/<path:case_id>', methods=['GET'])
def case_detail(case_id):
    """Return full case detail with steps and cluster info."""
    db = get_db()

    case_row = db.execute("SELECT * FROM test_cases WHERE id = ?", (case_id,)).fetchone()
    if not case_row:
        return jsonify({"success": False, "error": "用例未找到"}), 404

    extra = {}
    if case_row['extra_fields']:
        try:
            extra = json.loads(case_row['extra_fields'])
        except (json.JSONDecodeError, TypeError):
            pass

    # Get current active history_id for cluster results
    current_history = db.execute(
        "SELECT id FROM cluster_history WHERE is_current = 1 ORDER BY id DESC LIMIT 1"
    ).fetchone()
    history_id = current_history['id'] if current_history else None

    if history_id:
        step_rows = db.execute(
            "SELECT ts.*, cr.cluster_id, cr.cluster_label "
            "FROM test_steps ts "
            "LEFT JOIN cluster_results cr ON ts.id = cr.step_id AND cr.history_id = ? "
            "WHERE ts.case_id = ? ORDER BY ts.step_no",
            (history_id, case_id)
        ).fetchall()
    else:
        step_rows = db.execute(
            "SELECT ts.*, cr.cluster_id, cr.cluster_label "
            "FROM test_steps ts "
            "LEFT JOIN cluster_results cr ON ts.id = cr.step_id "
            "WHERE ts.case_id = ? ORDER BY ts.step_no",
            (case_id,)
        ).fetchall()

    steps = []
    for sr in step_rows:
        step_extra = {}
        if sr['extra_fields']:
            try:
                step_extra = json.loads(sr['extra_fields'])
            except (json.JSONDecodeError, TypeError):
                pass

        siblings = []
        if sr['cluster_id'] is not None and sr['cluster_id'] >= 0:
            if history_id:
                sib_rows = db.execute(
                    "SELECT ts.case_id, tc.title as case_title, ts.step_no, ts.operation "
                    "FROM cluster_results cr "
                    "JOIN test_steps ts ON cr.step_id = ts.id "
                    "JOIN test_cases tc ON ts.case_id = tc.id "
                    "WHERE cr.cluster_id = ? AND cr.step_id != ? AND cr.history_id = ? "
                    "LIMIT 10",
                    (sr['cluster_id'], sr['id'], history_id)
                ).fetchall()
            else:
                sib_rows = db.execute(
                    "SELECT ts.case_id, tc.title as case_title, ts.step_no, ts.operation "
                    "FROM cluster_results cr "
                    "JOIN test_steps ts ON cr.step_id = ts.id "
                    "JOIN test_cases tc ON ts.case_id = tc.id "
                    "WHERE cr.cluster_id = ? AND cr.step_id != ? "
                    "LIMIT 10",
                    (sr['cluster_id'], sr['id'])
                ).fetchall()
            siblings = [
                {
                    "case_id": s['case_id'],
                    "case_title": s['case_title'],
                    "step_no": s['step_no'],
                    "operation": s['operation'],
                }
                for s in sib_rows
            ]

        steps.append({
            "id": sr['id'],
            "step_no": sr['step_no'],
            "operation": sr['operation'],
            "extra_fields": step_extra,
            "cluster_id": sr['cluster_id'],
            "cluster_label": sr['cluster_label'],
            "siblings": siblings,
        })

    return jsonify({
        "success": True,
        "case": {
            "id": case_row['id'],
            "title": case_row['title'],
            "extra_fields": extra,
            "source_file": case_row['source_file'],
            "import_time": case_row['import_time'],
        },
        "steps": steps,
    })


@bp.route('/columns', methods=['GET'])
def available_columns():
    """Return all extra_fields keys found across cases and steps."""
    db = get_db()

    case_keys = set()
    step_keys = set()

    case_rows = db.execute(
        "SELECT DISTINCT extra_fields FROM test_cases WHERE extra_fields IS NOT NULL AND extra_fields != '{}'"
    ).fetchall()
    for row in case_rows:
        try:
            d = json.loads(row['extra_fields'])
            case_keys.update(d.keys())
        except (json.JSONDecodeError, TypeError):
            pass

    step_rows = db.execute(
        "SELECT DISTINCT extra_fields FROM test_steps WHERE extra_fields IS NOT NULL AND extra_fields != '{}'"
    ).fetchall()
    for row in step_rows:
        try:
            d = json.loads(row['extra_fields'])
            step_keys.update(d.keys())
        except (json.JSONDecodeError, TypeError):
            pass

    return jsonify({
        "success": True,
        "case_columns": sorted(case_keys),
        "step_columns": sorted(step_keys),
    })


# ---- Delete endpoints ----

@bp.route('/<path:case_id>', methods=['DELETE'])
def delete_case(case_id):
    """Delete a single case and its associated data."""
    db = get_db()

    case = db.execute("SELECT id FROM test_cases WHERE id = ?", (case_id,)).fetchone()
    if not case:
        return jsonify({"success": False, "error": "用例未找到"}), 404

    # Get step IDs for cascade cleanup
    step_ids = [r['id'] for r in db.execute("SELECT id FROM test_steps WHERE case_id = ?", (case_id,)).fetchall()]

    # Delete cluster results for these steps
    if step_ids:
        placeholders = ','.join('?' * len(step_ids))
        db.execute(f"DELETE FROM cluster_results WHERE step_id IN ({placeholders})", step_ids)

    # Delete steps and case (cascade should handle steps, but be explicit)
    db.execute("DELETE FROM test_steps WHERE case_id = ?", (case_id,))
    db.execute("DELETE FROM test_cases WHERE id = ?", (case_id,))
    db.commit()

    logger.info("Deleted case %s with %d steps", case_id, len(step_ids))
    return jsonify({"success": True, "deleted_steps": len(step_ids)})


@bp.route('/batch-delete', methods=['POST'])
def batch_delete_cases():
    """Delete multiple cases."""
    data = request.get_json() or {}
    case_ids = data.get('case_ids', [])

    if not case_ids:
        return jsonify({"success": False, "error": "未提供要删除的用例"}), 400

    db = get_db()
    total_steps = 0

    for case_id in case_ids:
        step_ids = [r['id'] for r in db.execute("SELECT id FROM test_steps WHERE case_id = ?", (case_id,)).fetchall()]
        if step_ids:
            placeholders = ','.join('?' * len(step_ids))
            db.execute(f"DELETE FROM cluster_results WHERE step_id IN ({placeholders})", step_ids)
        db.execute("DELETE FROM test_steps WHERE case_id = ?", (case_id,))
        db.execute("DELETE FROM test_cases WHERE id = ?", (case_id,))
        total_steps += len(step_ids)

    db.commit()
    logger.info("Batch deleted %d cases with %d steps", len(case_ids), total_steps)
    return jsonify({"success": True, "deleted_cases": len(case_ids), "deleted_steps": total_steps})


@bp.route('/all', methods=['DELETE'])
def clear_all_data():
    """Clear all cases, steps, and cluster results."""
    db = get_db()

    db.execute("DELETE FROM cluster_results")
    db.execute("DELETE FROM cluster_info")
    db.execute("DELETE FROM cluster_history")
    db.execute("DELETE FROM test_steps")
    db.execute("DELETE FROM test_cases")
    db.commit()

    logger.info("Cleared all data from database")
    return jsonify({"success": True})
