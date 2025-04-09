from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import weakref

class HTTPListener:
    def __init__(self, on_got_content_callback) -> None:
        self.callback = weakref.WeakMethod(on_got_content_callback)
        self.server = HTTPServer(("localhost", 2999), self.handler_factory(self.got_content))
        self.server.timeout = 0.05
        self.server_thread = WeakThreadLoop(self.handle, 0)

    def handle(self):
        self.server.handle_request()

    def got_content(self, content):
        method = self.callback()
        if method:
            method(content)

    def handler_factory(self, callback):
        class WebRequestHandler(BaseHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super(WebRequestHandler, self).__init__(*args, **kwargs)

            def do_POST(self):
                content_len = int(self.headers.get('Content-Length'))
                content = str(self.rfile.read(content_len))
                app.logger.info(f"http server got content: {content}")

                callback(content)

                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()

            def do_OPTIONS(self):
                return
    
            def log_message(self, format, *args):
                return

        return WebRequestHandler

class WeakThreadLoop(threading.Thread):
    def __init__(self, method, delay: float, name = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if name:
            self.name = name
        self.daemon = True
        self._delay = delay

        import weakref
        self._method = weakref.WeakMethod(method)
        self.start()

    def run(self):
        while self._method() is not None:
            self._method()()
            threading.Event().wait(self._delay)
        del self._method
