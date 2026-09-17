import threading
import time
import urllib.request

import uvicorn
import webview

from app.database import init_db
from app.main import app

HOST = "127.0.0.1"
PORT = 8765
URL = f"http://{HOST}:{PORT}"


class DesktopServer:
    def __init__(self):
        self.config = uvicorn.Config(app, host=HOST, port=PORT, log_level="warning", access_log=False)
        self.server = uvicorn.Server(self.config)
        self.thread = None

    def start(self):
        self.thread = threading.Thread(target=self.server.run, name="PrecificaEcomServer", daemon=True)
        self.thread.start()
        self._wait_until_ready()

    def _wait_until_ready(self, timeout=15):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(URL, timeout=0.5) as response:
                    if response.status < 500:
                        return
            except Exception:
                time.sleep(0.15)
        raise RuntimeError("O servidor interno do PrecificaEcom não iniciou a tempo.")

    def stop(self):
        self.server.should_exit = True
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=3)


def main():
    init_db()
    server = DesktopServer()
    server.start()

    window = webview.create_window(
        "PrecificaEcom",
        URL,
        width=1280,
        height=820,
        min_size=(960, 650),
        resizable=True,
        text_select=True,
    )

    window.events.closed += server.stop
    try:
        webview.start()
    finally:
        server.stop()


if __name__ == "__main__":
    main()
