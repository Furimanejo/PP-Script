import logging
import requests
import urllib3
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class HTTPHandler:
    def __init__(self, values: dict, logger: logging.Logger):
        self._logger = logger.getChild("http")
        self._port = int(values["port"])
        self._paths = {}
        for name, url in values.get("paths", {}).items():
            assert isinstance(url, str)
            self._paths[name] = f"{url}"
        if handle_content := values.get("handle_content"):
            self._launch_server(handle_content)

    def get(self, path_name):
        url = f"https://127.0.0.1:{self._port}/{self._paths[path_name]}"
        try:
            response = requests.get(url=url, verify=False, timeout=0.1)
            if 200 <= response.status_code <= 204:
                return {"httpStatus": response.status_code, "data": response.json()}
            return response.json()
        except Exception as e:
            return {"exception": str(e)}

    def _launch_server(self, handle_content):
        class POSTHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                content_len = int(self.headers.get("Content-Length", 0))
                content = self.rfile.read(content_len)
                content_type = self.headers.get("Content-Type", "")
                if content_type.startswith("text/plain"):
                    content = content.decode("utf-8")

                handle_content(content)

                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(b"Received")

            def do_OPTIONS(self):
                return

            def log_message(self, format, *args):
                return

        server = HTTPServer(("localhost", self._port), POSTHandler)

        def serve():
            server.serve_forever()

        self.handle_post_thread = threading.Thread(target=serve, daemon=True)
        self.handle_post_thread.start()

    def __del__(self):
        print("A")
