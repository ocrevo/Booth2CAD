"""Serve the editor on localhost for testing (browsers refuse ES modules from file://).

    python web/tools/serve.py            # http://127.0.0.1:8000/ and opens the browser
    python web/tools/serve.py --port 8765 --no-browser

Only web/app is served, only to this machine. Nothing is uploaded anywhere.
"""
from __future__ import annotations
import argparse
import functools
import http.server
import threading
import webbrowser
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / 'app'


class Handler(http.server.SimpleHTTPRequestHandler):
    # Windows' registry can map .js to text/plain, which browsers refuse for module scripts.
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json',
                      '.css': 'text/css', '.html': 'text/html', '.png': 'image/png', '.glb': 'model/gltf-binary'}

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def log_message(self, fmt, *args):
        if self.server.verbose:
            super().log_message(fmt, *args)


class Server(http.server.ThreadingHTTPServer):
    verbose = False
    request_queue_size = 128   # the default of 5 overflows when a browser fetches many modules at once (connection refused on Windows)


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--port', type=int, default=8000)
    p.add_argument('--no-browser', action='store_true')
    p.add_argument('--verbose', action='store_true')
    a = p.parse_args()
    server = Server(('127.0.0.1', a.port), functools.partial(Handler, directory=str(APP)))
    server.verbose = a.verbose
    url = f'http://127.0.0.1:{a.port}/'
    print(f'Serving {APP} at {url}  (Ctrl+C to stop)')
    if not a.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('stopped')


if __name__ == '__main__':
    main()
