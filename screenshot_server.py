#!/usr/bin/env python3
"""Minimal screenshot server for Xvfb display capture."""
import base64
import json
import subprocess
import tempfile
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

DISPLAY = os.environ.get("DISPLAY", ":99")

class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/screenshot" or self.path.startswith("/screenshot?"):
            self._screenshot()
        elif self.path == "/health":
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
        else:
            self.send_response(404)
            self.end_headers()

    def _screenshot(self):
        try:
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
                tmp = f.name
            subprocess.run(
                ["scrot", "-o", "-q", "60", tmp],
                env={**os.environ, "DISPLAY": DISPLAY},
                timeout=5,
                check=True,
            )
            with open(tmp, "rb") as f:
                data = base64.b64encode(f.read()).decode()
            os.unlink(tmp)
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"image": data}).encode())
        except Exception as e:
            self.send_response(500)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")

    def log_message(self, fmt, *args):
        pass

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "3001"))
    print(f"Screenshot server on :{port} (display={DISPLAY})")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
