#!/usr/bin/env python3
"""
Woolly Goose proxy server.
Serves static files + proxies /api/messages → Anthropic (API key stays server-side).

Env vars:
  ANTHROPIC_API_KEY  (required)
  ACCESS_CODE        (optional — if set, clients must send matching x-access-code header)
  PORT               (optional — defaults to 8765)
"""
import collections
import http.client
import os
import ssl
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler

# ── Config ─────────────────────────────────────────────────────────────────────
API_KEY     = os.environ['ANTHROPIC_API_KEY']        # crash fast if missing
ACCESS_CODE = os.environ.get('ACCESS_CODE', '')      # empty = gate disabled
PORT        = int(os.environ.get('PORT', 8765))

ANTHROPIC_HOST = 'api.anthropic.com'
ANTHROPIC_PATH = '/v1/messages'

# ── Rate limiting: 20 API calls per IP per 10 minutes ─────────────────────────
_RATE_WINDOW  = 600
_RATE_LIMIT   = 20
_rate_lock    = threading.Lock()
_rate_buckets = collections.defaultdict(list)

def _allow(ip):
    now = time.monotonic()
    cutoff = now - _RATE_WINDOW
    with _rate_lock:
        _rate_buckets[ip] = [t for t in _rate_buckets[ip] if t > cutoff]
        if len(_rate_buckets[ip]) >= _RATE_LIMIT:
            return False
        _rate_buckets[ip].append(now)
        return True

# ── Handler ────────────────────────────────────────────────────────────────────
class Handler(SimpleHTTPRequestHandler):
    def do_OPTIONS(self):
        self._send_cors(200)

    def do_POST(self):
        if self.path == '/api/messages':
            self._proxy()
        else:
            self.send_error(404)

    def _send_cors(self, status, extra_headers=None):
        self.send_response(status)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers',
                         'content-type,anthropic-version,x-access-code')
        if extra_headers:
            for k, v in extra_headers:
                self.send_header(k, v)
        self.end_headers()

    def _proxy(self):
        ip = self.client_address[0]

        # Access code gate (skipped when ACCESS_CODE is empty)
        if ACCESS_CODE and self.headers.get('x-access-code', '') != ACCESS_CODE:
            self.send_error(403, 'Invalid or missing access code')
            return

        # Rate limit
        if not _allow(ip):
            self.send_error(429, 'Rate limit reached — try again in 10 minutes')
            return

        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)

        forward = {
            'x-api-key':          API_KEY,
            'anthropic-version':  self.headers.get('anthropic-version', '2023-06-01'),
            'content-type':       'application/json',
        }

        ctx = ssl.create_default_context()
        conn = http.client.HTTPSConnection(ANTHROPIC_HOST, context=ctx)
        try:
            conn.request('POST', ANTHROPIC_PATH, body, forward)
            resp = conn.getresponse()

            self.send_response(resp.status)
            self.send_header('Access-Control-Allow-Origin', '*')
            for k, v in resp.getheaders():
                if k.lower() not in ('transfer-encoding', 'connection', 'content-length'):
                    self.send_header(k, v)
            self.end_headers()

            while True:
                chunk = resp.read(4096)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except Exception as e:
            self.send_error(502, f'Upstream error: {e}')
        finally:
            conn.close()

    def log_message(self, fmt, *args):
        pass  # quiet

# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', PORT), Handler)
    print(f'Woolly Goose → http://localhost:{PORT}/woolly-goose.html')
    server.serve_forever()
