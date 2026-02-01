import os
import logging
from flask import Flask, jsonify

from app.config import Config
from app.logger import setup_logging
from app.database import init_db
from app.routes import register_blueprints

logger = logging.getLogger(__name__)


def create_app(config_override=None):
    app = Flask(
        __name__,
        template_folder='templates',
        static_folder=os.path.join(Config.BASE_DIR, 'static'),
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
