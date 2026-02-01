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


@bp.route('/<path:case_id>', methods=['GET'])
def case_detail(case_id):
    """Return full case detail with steps and cluster info."""
    db = get_db()

    case_row = db.execute("SELECT * FROM test_cases WHERE id = ?", (case_id,)).fetchone()
    if not case_row:
        return jsonify({"success": False, "error": "Case not found"}), 404

    extra = {}
    if case_row['extra_fields']:
        try:
            extra = json.loads(case_row['extra_fields'])
        except (json.JSONDecodeError, TypeError):
            pass

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
