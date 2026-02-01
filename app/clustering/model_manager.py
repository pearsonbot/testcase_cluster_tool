import logging

logger = logging.getLogger(__name__)


class ModelManager:
    """Singleton-like manager that holds the current embedding model."""

    _instance = None
    _current_config = {}

    @classmethod
    def get_model(cls, config=None):
        """Get the current model. If config differs from current, recreate.

        Args:
            config: dict with keys: model_type, model_path, api_url, api_key,
                    api_model_name, builtin_model_path
        """
        if config and config != cls._current_config:
            cls._instance = cls.create_model(config)
            cls._current_config = config.copy()

        if cls._instance is None:
            if config:
                cls._instance = cls.create_model(config)
                cls._current_config = config.copy()
            else:
                raise RuntimeError("No embedding model configured. Please go to Settings to configure a model.")

        return cls._instance

    @classmethod
    def create_model(cls, config):
        """Create a new model instance from config (without caching)."""
        model_type = config.get("model_type", "builtin")

        if model_type == "builtin":
            from app.clustering.embedding_builtin import BuiltinEmbeddingModel
            model_path = config.get("builtin_model_path", "")
            if not model_path:
                raise ValueError("Built-in model path is not configured")
            return BuiltinEmbeddingModel(model_path)

        elif model_type == "local":
            from app.clustering.embedding_local import LocalPathEmbeddingModel
            model_path = config.get("model_path", "")
            if not model_path:
                raise ValueError("Local model path is not specified")
            return LocalPathEmbeddingModel(model_path)

        elif model_type == "api":
            from app.clustering.embedding_api import OnlineAPIEmbeddingModel
            api_url = config.get("api_url", "")
            api_key = config.get("api_key", "")
            api_model_name = config.get("api_model_name", "")
            if not api_url:
                raise ValueError("API URL is not specified")
            if not api_key:
                raise ValueError("API Key is not specified")
            if not api_model_name:
                raise ValueError("API model name is not specified")
            return OnlineAPIEmbeddingModel(api_url, api_key, api_model_name)

        elif model_type == "tfidf":
            from app.clustering.embedding_tfidf import TfidfEmbeddingModel
            return TfidfEmbeddingModel()

        else:
            raise ValueError(f"Unknown model type: {model_type}")

    @classmethod
    def release(cls):
        """Release the model from memory."""
        cls._instance = None
        cls._current_config = {}
        logger.info("Model released from memory")
