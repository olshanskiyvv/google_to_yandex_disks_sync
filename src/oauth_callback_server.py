import asyncio
import http.server
import socket
import socketserver
import threading
import time
from typing import Any
from urllib.parse import parse_qs, urlparse


class OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    code: str | None = None
    error: str | None = None

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/callback":
            params = parse_qs(parsed.query)

            if "code" in params:
                OAuthCallbackHandler.code = params["code"][0]
                self._send_success_response()
            elif "error" in params:
                OAuthCallbackHandler.error = params["error"][0]
                self._send_error_response(params["error"][0])
            else:
                self.send_response(400)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def _send_success_response(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        html = """
<!DOCTYPE html>
<html>
<head><title>Авторизация успешна</title></head>
<body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
    <h1 style="color: #4CAF50;">Авторизация успешна!</h1>
    <p>Вы можете закрыть это окно и вернуться к приложению.</p>
</body>
</html>
        """
        self.wfile.write(html.encode("utf-8"))

    def _send_error_response(self, error: str) -> None:
        self.send_response(400)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        html = f"""
<!DOCTYPE html>
<html>
<head><title>Ошибка авторизации</title></head>
<body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
    <h1 style="color: #f44336;">Ошибка авторизации</h1>
    <p>{error}</p>
</body>
</html>
        """
        self.wfile.write(html.encode("utf-8"))

    def log_message(self, format: str, *args: Any) -> None:
        pass


class OAuthServer:
    def __init__(self, port: int | None = None):
        self.port = port or self._find_free_port()
        self._server: socketserver.TCPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def redirect_uri(self) -> str:
        return f"http://localhost:{self.port}/callback"

    def start(self) -> None:
        OAuthCallbackHandler.code = None
        OAuthCallbackHandler.error = None

        self._server = socketserver.TCPServer(("", self.port), OAuthCallbackHandler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    async def wait_for_code(self, timeout: float = 120.0) -> str:
        start_time = time.time()

        while OAuthCallbackHandler.code is None and OAuthCallbackHandler.error is None:
            if time.time() - start_time > timeout:
                self.stop()
                raise TimeoutError(f"Таймаут ожидания авторизации ({timeout} секунд)")
            await asyncio.sleep(0.5)

        self.stop()

        if OAuthCallbackHandler.error:
            raise ValueError(f"Ошибка авторизации: {OAuthCallbackHandler.error}")

        if not OAuthCallbackHandler.code:
            raise ValueError("Код авторизации не получен")

        return OAuthCallbackHandler.code

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server = None
            self._thread = None

    @staticmethod
    def _find_free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            s.listen(1)
            return s.getsockname()[1]
