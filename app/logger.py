import os
import logging
from logging.handlers import TimedRotatingFileHandler


def setup_logging(app):
    log_dir = app.config.get("LOG_DIR", "log")
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, "app.log")

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(module)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler = TimedRotatingFileHandler(
        log_file,
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8"
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.namer = lambda name: _custom_namer(name, log_dir)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    # Avoid adding duplicate handlers on reload
    if not root_logger.handlers:
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)


def _custom_namer(default_name, log_dir):
    """Transform 'app.log.2025-01-15' to 'app_2025-01-15.log'."""
    # default_name looks like: /path/to/log/app.log.2025-01-15
    basename = os.path.basename(default_name)
    parts = basename.split(".")
    if len(parts) >= 3:
        # parts = ['app', 'log', '2025-01-15']
        date_suffix = parts[-1]
        return os.path.join(log_dir, f"app_{date_suffix}.log")
    return default_name
