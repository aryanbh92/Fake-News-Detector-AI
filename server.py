"""Serve the Fake News Detector prototype and proxy analysis API calls."""

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from functools import partial
from urllib import error as urllib_error
from urllib import request as urllib_request


ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = 8000
API_HOST = "127.0.0.1"
API_PORT = 9000
API_BASE = f"http://{API_HOST}:{API_PORT}"


class ProxyRequestHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/api/"):
            self._proxy_api_request()
            return
        super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/"):
            self._proxy_api_request()
            return
        super().do_POST()

    def _proxy_api_request(self):
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length) if content_length else b""
            target_url = f"{API_BASE}{self.path}"
            headers = {"Content-Type": self.headers.get("Content-Type", "application/json")}
            if self.headers.get("Accept"):
                headers["Accept"] = self.headers.get("Accept")

            proxied_req = urllib_request.Request(
                target_url,
                data=body,
                headers=headers,
                method=self.command,
            )
            with urllib_request.urlopen(proxied_req, timeout=50) as response:
                payload = response.read()
                content_type = response.headers.get_content_type()
                self.send_response(response.status)
                self.send_header("Content-Type", content_type or "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
        except urllib_error.HTTPError as error:
            payload = error.read()
            self.send_response(error.code)
            self.send_header("Content-Type", error.headers.get("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except (urllib_error.URLError, TimeoutError, OSError):
            payload = b'{"error":"The local analysis API is unavailable. Check that api_server.py is running."}'
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

def main():
    handler = partial(ProxyRequestHandler, directory=str(ROOT))
    server = ThreadingHTTPServer((HOST, PORT), handler)
    print(f"Fake News Detector is running at http://{HOST}:{PORT}")
    print(f"Proxying /api/* requests to http://{API_HOST}:{API_PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Fake News Detector.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
