import http.server
import socketserver
import os
import sys
import json
import urllib.request
import urllib.error
from urllib.parse import urlsplit

PORT = int(os.environ.get("PORT", 10000))
DASHBOARD_PORT = int(os.environ.get("API_SERVER_PORT", 8642))
DASHBOARD_URL = f"http://127.0.0.1:{DASHBOARD_PORT}"
MODEL_CHOICES = (
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
)

DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Hermes Agent</title>
    <style>
        :root { color-scheme: dark; --bg: #10131a; --panel: #191e29; --line: #30394a; --text: #f1f4f8; --muted: #9ca8bb; --accent: #f0c94b; }
        * { box-sizing: border-box; }
        body { margin: 0; min-height: 100vh; background: radial-gradient(circle at top right, #27334b, var(--bg) 45%); color: var(--text); font: 16px/1.5 system-ui, sans-serif; }
        main { width: min(920px, 100%); margin: auto; padding: 40px 20px; }
        header { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 24px; }
        h1 { margin: 0; font-size: clamp(1.8rem, 5vw, 3rem); letter-spacing: .02em; }
        .status { color: var(--muted); font-size: .9rem; }
        .panel { background: color-mix(in srgb, var(--panel) 92%, transparent); border: 1px solid var(--line); border-radius: 10px; padding: 20px; box-shadow: 0 18px 50px #0004; }
        label { display: block; color: var(--muted); font-size: .85rem; margin-bottom: 7px; }
        select, textarea, button { width: 100%; border: 1px solid var(--line); border-radius: 7px; background: #0f131b; color: var(--text); font: inherit; padding: 11px 12px; }
        textarea { min-height: 140px; resize: vertical; margin-top: 18px; }
        button { width: auto; margin-top: 14px; background: var(--accent); color: #18150a; border-color: var(--accent); font-weight: 700; cursor: pointer; }
        button:disabled { cursor: wait; opacity: .6; }
        pre { white-space: pre-wrap; margin: 20px 0 0; padding: 16px; min-height: 80px; background: #0b0e14; border: 1px solid var(--line); border-radius: 7px; }
        .hint { color: var(--muted); font-size: .85rem; margin: 14px 0 0; }
    </style>
</head>
<body>
    <main>
        <header><h1>Hermes Agent</h1><span class="status" id="status">Checking service...</span></header>
        <section class="panel">
            <label for="model">Model for this request</label>
            <select id="model"></select>
            <textarea id="prompt" placeholder="Ask Hermes something..."></textarea>
            <button id="send">Send request</button>
            <pre id="answer">Responses will appear here.</pre>
            <p class="hint">The available choices depend on the configured Hermes provider and its API access. Free-tier availability is controlled by that provider.</p>
        </section>
    </main>
    <script>
        const choices = __MODEL_CHOICES__;
        const model = document.querySelector('#model');
        const prompt = document.querySelector('#prompt');
        const answer = document.querySelector('#answer');
        const send = document.querySelector('#send');
        const status = document.querySelector('#status');
        const setModels = names => { model.replaceChildren(...names.map(name => new Option(name, name))); };
        setModels(choices);
        fetch('/v1/models').then(response => response.ok ? response.json() : Promise.reject()).then(data => {
            const names = (data.data || []).map(item => item.id).filter(Boolean);
            if (names.length) setModels(names);
        }).catch(() => {});
        fetch('/health').then(response => { status.textContent = response.ok ? 'Service online' : 'Service unavailable'; }).catch(() => status.textContent = 'Service unavailable');
        send.addEventListener('click', async () => {
            if (!prompt.value.trim()) return;
            send.disabled = true; answer.textContent = 'Thinking...';
            try {
                const response = await fetch('/v1/chat/completions', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({model: model.value, messages: [{role: 'user', content: prompt.value}], stream: false}) });
                const data = await response.json();
                if (!response.ok) throw new Error(data.error?.message || data.message || `Request failed (${response.status})`);
                answer.textContent = data.choices?.[0]?.message?.content || JSON.stringify(data, null, 2);
            } catch (error) { answer.textContent = error.message; }
            finally { send.disabled = false; }
        });
    </script>
</body>
</html>"""


class ProxyAndHealthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if urlsplit(self.path).path == "/":
            content = DASHBOARD_HTML.replace("__MODEL_CHOICES__", json.dumps(MODEL_CHOICES)).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

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
