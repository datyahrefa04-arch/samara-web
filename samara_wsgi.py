"""Adaptor WSGI supaya server.py SAMARA bisa jalan di PythonAnywhere (hosting gratis tanpa kartu).

Tidak mengubah logika server.py: setiap request WSGI diubah menjadi request HTTP mentah,
diproses oleh handler yang sama, lalu hasilnya dikembalikan lagi ke WSGI.
"""
import io
import os
from urllib.parse import quote

import server

server.initialize_database()
if os.environ.get("SAMARA_ADMIN_PASSWORD"):
    server.ensure_admin_password()


class _FakeServer:
    server_name = "samara"
    server_port = 80


class _WsgiHandler(server.SmartWargaHandler):
    def __init__(self, raw_request, client_address):
        # Sengaja tidak memanggil __init__ bawaan (tidak ada socket di WSGI).
        self.rfile = io.BytesIO(raw_request)
        self.wfile = io.BytesIO()
        self.client_address = client_address
        self.server = _FakeServer()
        self.close_connection = True
        self.handle_one_request()


def application(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET")
    target = environ.get("REQUEST_URI")
    if not target:
        target = quote(environ.get("PATH_INFO", "/")) or "/"
        if environ.get("QUERY_STRING"):
            target += "?" + environ["QUERY_STRING"]

    length = int(environ.get("CONTENT_LENGTH") or 0)
    body = environ["wsgi.input"].read(length) if length > 0 else b""

    lines = [f"{method} {target} HTTP/1.1"]
    for key, value in environ.items():
        if key.startswith("HTTP_"):
            lines.append(f"{key[5:].replace('_', '-').title()}: {value}")
    if environ.get("CONTENT_TYPE"):
        lines.append(f"Content-Type: {environ['CONTENT_TYPE']}")
    lines.append(f"Content-Length: {len(body)}")
    raw = ("\r\n".join(lines) + "\r\n\r\n").encode("latin-1") + body

    handler = _WsgiHandler(raw, (environ.get("REMOTE_ADDR", "0.0.0.0"), 0))
    response = handler.wfile.getvalue()
    head, _, payload = response.partition(b"\r\n\r\n")
    head_lines = head.decode("latin-1").split("\r\n")
    status = head_lines[0].split(" ", 1)[1]
    headers = [tuple(line.split(": ", 1)) for line in head_lines[1:] if ": " in line]
    start_response(status, headers)
    return [payload]
