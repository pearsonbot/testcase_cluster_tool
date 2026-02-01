import os
import sys
import webbrowser
import threading
import logging

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.config import Config

logger = logging.getLogger(__name__)


def main():
    os.makedirs(os.path.join(Config.BASE_DIR, "data"), exist_ok=True)
    os.makedirs(os.path.join(Config.BASE_DIR, "log"), exist_ok=True)

    app = create_app()

    host = "127.0.0.1"
    port = 5000
    url = f"http://{host}:{port}"

    threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    logger.info("Starting server at %s", url)
    print(f"Server running at {url}")
    print("Press Ctrl+C to stop.")

    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
