import logging

from flask import Blueprint, request, jsonify
from app.database import get_db, get_setting, set_setting

logger = logging.getLogger(__name__)

bp = Blueprint('settings_api', __name__, url_prefix='/api/settings')

SETTING_KEYS = ['model_type', 'model_path', 'api_url', 'api_key', 'api_model_name']


@bp.route('/', methods=['GET'])
def get_settings():
    """Return current settings."""
    settings = {}
    for key in SETTING_KEYS:
        settings[key] = get_setting(key, '')
    if not settings.get('model_type'):
        settings['model_type'] = 'builtin'
    return jsonify({"success": True, "settings": settings})


@bp.route('/', methods=['PUT'])
def update_settings():
    """Update settings."""
    data = request.get_json() or {}

    for key in SETTING_KEYS:
        if key in data:
            set_setting(key, data[key])

    # Release current model so it reloads with new config
    from app.clustering.model_manager import ModelManager
    ModelManager.release()

    logger.info("Settings updated: model_type=%s", data.get('model_type', ''))
    return jsonify({"success": True})


@bp.route('/test-model', methods=['POST'])
def test_model():
    """Test model connection with a sample text."""
    data = request.get_json() or {}

    try:
        from app.clustering.model_manager import ModelManager
        from flask import current_app

        model_config = {
            "model_type": data.get("model_type", "builtin"),
            "model_path": data.get("model_path", ""),
            "api_url": data.get("api_url", ""),
            "api_key": data.get("api_key", ""),
            "api_model_name": data.get("api_model_name", ""),
            "builtin_model_path": current_app.config['BUILTIN_MODEL_PATH'],
        }

        model = ModelManager.create_model(model_config)
        result = model.encode(["This is a test sentence."])
        dim = result.shape[1] if len(result.shape) > 1 else len(result[0])

        return jsonify({
            "success": True,
            "dimension": int(dim),
            "model_name": model.model_name,
        })
    except Exception as e:
        logger.error("Model test failed: %s", e, exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 400
