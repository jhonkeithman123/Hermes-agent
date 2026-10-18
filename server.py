import http.server
import socketserver
import os
import sys
import urllib.request
import urllib.error

PORT = int(os.environ.get("PORT", 10000))
DASHBOARD_URL = "http://127.0.0.1:9119"


class ProxyAndHealthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        # Health check endpoint for Render and external cronjobs
        if self.path in ("/health", "/healthz", "/ping"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok","service":"hermes-agent"}')
            return

        # Reverse proxy other requests to the internal Hermes dashboard (127.0.0.1:9119)
        target_url = f"{DASHBOARD_URL}{self.path}"
        try:
            req = urllib.request.Request(
                target_url,
                headers={k: v for k, v in self.headers.items() if k.lower() != "host"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                self.send_response(resp.status)
                for k, v in resp.getheaders():
                    if k.lower() not in ("transfer-encoding", "content-length"):
                        self.send_header(k, v)
                content = resp.read()
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
        except urllib.error.HTTPError as error:
            self.send_response(error.code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(f'{{"status":"error","message":"Dashboard returned HTTP {error.code}"}}'.encode())
        except (urllib.error.URLError, TimeoutError) as error:
            print(f"Dashboard unavailable for GET {self.path}: {error}", flush=True)
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"error","message":"Hermes dashboard is unavailable"}')

    def do_POST(self):
        if self.path in ("/health", "/healthz", "/ping"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
            return

        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else None
        target_url = f"{DASHBOARD_URL}{self.path}"
        try:
            req = urllib.request.Request(
                target_url,
                data=post_data,
                headers={k: v for k, v in self.headers.items() if k.lower() != "host"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                self.send_response(resp.status)
                for k, v in resp.getheaders():
                    if k.lower() not in ("transfer-encoding", "content-length"):
                        self.send_header(k, v)
                content = resp.read()
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
        except urllib.error.HTTPError as error:
            self.send_response(error.code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
        except (urllib.error.URLError, TimeoutError) as error:
            print(f"Dashboard unavailable for POST {self.path}: {error}", flush=True)
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"error","message":"Hermes dashboard is unavailable"}')

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

if __name__ == "__main__":
    print(f"Keep-alive & health server listening on 0.0.0.0:{PORT}", flush=True)

    class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
        allow_reuse_address = True
        daemon_threads = True

    with ThreadingTCPServer(("0.0.0.0", PORT), ProxyAndHealthHandler) as httpd:
        httpd.serve_forever()
