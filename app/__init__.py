import os
import sys
import logging
from flask import Flask, jsonify

from app.config import Config
from app.logger import setup_logging
from app.database import init_db
from app.routes import register_blueprints

logger = logging.getLogger(__name__)


def _get_resource_path(relative_path):
    """Get path to bundled resource, works for dev and PyInstaller."""
    if getattr(sys, 'frozen', False):
        # PyInstaller puts data files in _internal/ (PyInstaller 6+)
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
        base = os.path.dirname(base)  # project root
    return os.path.join(base, relative_path)


def create_app(config_override=None):
    template_dir = _get_resource_path(os.path.join('app', 'templates'))
    static_dir = _get_resource_path('static')

    app = Flask(
        __name__,
        template_folder=template_dir,
        static_folder=static_dir,
        static_url_path='/static'
    )

    app.config.from_object(Config)
    if config_override:
        app.config.update(config_override)

    setup_logging(app)
    init_db(app)
    register_blueprints(app)

    @app.errorhandler(404)
    def not_found(e):
        if 'api' in str(getattr(e, 'description', '')):
            return jsonify({"success": False, "error": "Not found"}), 404
        return jsonify({"success": False, "error": "Page not found"}), 404

    @app.errorhandler(500)
    def internal_error(e):
        logger.error("Internal server error: %s", e, exc_info=True)
        return jsonify({"success": False, "error": "Internal server error"}), 500

    return app
