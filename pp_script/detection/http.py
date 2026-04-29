import logging
import requests
import urllib3
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import socket
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def ensure_can_bind_to(address: tuple[str, int]):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(address)


class HTTPHandler:
    def __init__(self, values: dict, logger: logging.Logger, lib_version: int):
        self._logger = logger.getChild("http")
        self._LIB_VERSION = lib_version

        self.thread_lock = threading.Lock()
        self._server: HTTPServer = None  # type: ignore
        if handle_content := values.get("handle_content"):
            port = int(values["port"])
            self._launch_server(port, handle_content)

        if self._LIB_VERSION <= 2:
            port = int(values["port"])
            self._paths = {}
            for name, path in values.get("paths", {}).items():
                assert isinstance(path, str)
                self._paths[name] = f"https://127.0.0.1:{port}/{path}"

    def get(self, url: str, timeout=0.1) -> dict:
        ALLOWED_URL_STARTS = [
            "http://127.0.0.1",
            "https://127.0.0.1",
        ]
        for url_start in ALLOWED_URL_STARTS:
            if url.startswith(url_start):
                break
        else:
            raise Exception(f"Invalid URL, not within: {ALLOWED_URL_STARTS}")

        try:
            response = requests.get(url=url, verify=False, timeout=timeout)
            return {"status_code": response.status_code, "content": response.json()}
        except Exception as e:
            return {"exception": str(e)}

    def _get_v2(self, path_name):
        url = self._paths[path_name]
        try:
            response = requests.get(url=url, verify=False, timeout=0.1)
            if 200 <= response.status_code <= 204:
                return {"http_status": response.status_code, "data": response.json()}
            return response.json()
        except Exception as e:
            return {"exception": str(e)}

    def _launch_server(self, port: int, handle_content):
        address = ("localhost", port)
        try:
            ensure_can_bind_to(address=address)
        except Exception as e:
            raise Exception(f"Failed to bind to address={address}: {e}") from e

        lock = self.thread_lock
        LIB_VERSION = self._LIB_VERSION

        class POSTHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                content_len = int(self.headers.get("Content-Length", 0))
                content = self.rfile.read(content_len)
                print(content)
                content_type = self.headers.get("Content-Type", "")
                if content_type.startswith("text/plain"):
                    content = content.decode("utf-8")
                elif content_type.startswith("application/json") and LIB_VERSION >= 3:
                    content = json.loads(content)

                response = b"PP OK"
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)

                with lock:
                    handle_content(content)

            def do_OPTIONS(self):
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.end_headers()

            def log_message(self, format, *args):
                return

        self._server = HTTPServer(address, POSTHandler)

        def serve():
            self._server.serve_forever()

        self.handle_post_thread = threading.Thread(target=serve, daemon=True)
        self.handle_post_thread.start()

    def terminate(self):
        if self._server:
            self._server.shutdown()
            self._server.server_close()
