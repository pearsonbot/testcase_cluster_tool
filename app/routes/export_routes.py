import io
import zipfile
import logging

from flask import Blueprint, request, jsonify, send_file
from app.database import get_db
from app.exporter.xlsx_exporter import XlsxExporter

logger = logging.getLogger(__name__)

bp = Blueprint('export_api', __name__, url_prefix='/api/export')


@bp.route('/', methods=['POST'])
def export_results():
    """Export clustering results as a zip containing xlsx files."""
    db = get_db()

    cluster_count = db.execute("SELECT COUNT(*) as cnt FROM cluster_info").fetchone()['cnt']
    if cluster_count == 0:
        return jsonify({"success": False, "error": "No clustering results to export. Please run clustering first."}), 400

    try:
        exporter = XlsxExporter(db)
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            overview_bytes = exporter.export_overview()
            zf.writestr("聚类总览.xlsx", overview_bytes)

            detail_bytes = exporter.export_cluster_details()
            zf.writestr("簇详情.xlsx", detail_bytes)

            case_view_bytes = exporter.export_case_cluster_view()
            zf.writestr("用例聚类视图.xlsx", case_view_bytes)

        zip_buffer.seek(0)
        logger.info("Export completed successfully")

        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name='clustering_results.zip'
        )

    except Exception as e:
        logger.error("Export failed: %s", e, exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500
