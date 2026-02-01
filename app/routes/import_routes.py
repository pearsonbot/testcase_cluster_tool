import os
import json
import logging
import tempfile
from datetime import datetime

from flask import Blueprint, request, jsonify, current_app
from app.database import get_db
from app.importer.column_mapper import ColumnMapper
from app.importer.xlsx_reader import XlsxReader
from app.importer.data_validator import DataValidator

logger = logging.getLogger(__name__)

bp = Blueprint('import_api', __name__, url_prefix='/api/import')

# Temporary storage for upload session
_upload_session = {}


@bp.route('/upload', methods=['POST'])
def upload_xlsx():
    """Receive xlsx file, detect column mapping, return for confirmation."""
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No file provided"}), 400

    file = request.files['file']
    if not file.filename or not file.filename.endswith('.xlsx'):
        return jsonify({"success": False, "error": "Please upload an xlsx file"}), 400

    upload_dir = current_app.config.get('UPLOAD_FOLDER', tempfile.gettempdir())
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, file.filename)
    file.save(filepath)
    logger.info("Uploaded file saved: %s", filepath)

    try:
        mapper = ColumnMapper(filepath)
        headers = mapper.headers
        mapping, unmatched = mapper.auto_detect()
        extra_columns = mapper.extra_columns

        _upload_session['filepath'] = filepath
        _upload_session['filename'] = file.filename
        _upload_session['headers'] = headers
        _upload_session['mapping'] = mapping
        _upload_session['extra_columns'] = extra_columns

        return jsonify({
            "success": True,
            "headers": headers,
            "mapping": mapping,
            "unmatched": unmatched,
            "extra_columns": extra_columns,
            "auto_confirmed": len(unmatched) == 0
        })
    except Exception as e:
        logger.error("Failed to analyze xlsx: %s", e, exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/confirm', methods=['POST'])
def confirm_import():
    """Execute import with confirmed column mapping."""
    if 'filepath' not in _upload_session:
        return jsonify({"success": False, "error": "No file uploaded. Please upload first."}), 400

    data = request.get_json() or {}
    mapping = data.get('mapping', _upload_session.get('mapping', {}))

    filepath = _upload_session['filepath']
    filename = _upload_session['filename']

    try:
        reader = XlsxReader(filepath, mapping)
        cases_with_steps = reader.read_all()

        validator = DataValidator()
        result = validator.validate(cases_with_steps)

        if result.errors:
            return jsonify({
                "success": False,
                "errors": result.errors,
                "warnings": result.warnings
            }), 400

        db = get_db()
        now = datetime.now().isoformat()
        cases_imported = 0
        steps_imported = 0

        for case, steps in result.valid_cases:
            # Delete existing case and its steps (incremental import)
            db.execute("DELETE FROM test_steps WHERE case_id = ?", (case.id,))
            db.execute("DELETE FROM test_cases WHERE id = ?", (case.id,))

            db.execute(
                "INSERT INTO test_cases (id, title, extra_fields, source_file, import_time) VALUES (?, ?, ?, ?, ?)",
                (case.id, case.title, json.dumps(case.extra_fields, ensure_ascii=False), filename, now)
            )
            cases_imported += 1

            for step in steps:
                db.execute(
                    "INSERT INTO test_steps (case_id, step_no, operation, extra_fields) VALUES (?, ?, ?, ?)",
                    (case.id, step.step_no, step.operation,
                     json.dumps(step.extra_fields, ensure_ascii=False))
                )
                steps_imported += 1

        # Clear stale cluster results
        db.execute("DELETE FROM cluster_results")
        db.execute("DELETE FROM cluster_info")
        db.commit()

        logger.info("Import completed: %s, cases=%d, steps=%d", filename, cases_imported, steps_imported)

        _upload_session.clear()

        return jsonify({
            "success": True,
            "cases_imported": cases_imported,
            "steps_imported": steps_imported,
            "warnings": result.warnings
        })

    except Exception as e:
        logger.error("Import failed: %s", e, exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/status', methods=['GET'])
def import_status():
    """Return current DB statistics."""
    try:
        db = get_db()
        case_count = db.execute("SELECT COUNT(*) as cnt FROM test_cases").fetchone()['cnt']
        step_count = db.execute("SELECT COUNT(*) as cnt FROM test_steps").fetchone()['cnt']
        last_import = db.execute(
            "SELECT import_time FROM test_cases ORDER BY import_time DESC LIMIT 1"
        ).fetchone()
        cluster_count = db.execute("SELECT COUNT(*) as cnt FROM cluster_info").fetchone()['cnt']

        return jsonify({
            "success": True,
            "case_count": case_count,
            "step_count": step_count,
            "last_import_time": last_import['import_time'] if last_import else None,
            "cluster_count": cluster_count
        })
    except Exception as e:
        logger.error("Failed to get import status: %s", e, exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500
