"""Serve only the browser check and canonical probe on localhost for 120 seconds."""
import functools
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from time import monotonic

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
with TemporaryDirectory(prefix="hg-webgl2-browser-") as temporary:
    document_root = Path(temporary)
    page = (HERE / "browser_check.html").read_text().replace("../../web_probe/canonical_web_probe.js", "canonical_web_probe.js")
    (document_root / "index.html").write_text(page)
    shutil.copyfile(ROOT / "web_probe/canonical_web_probe.js", document_root / "canonical_web_probe.js")
    server = HTTPServer(("127.0.0.1", 8766), functools.partial(SimpleHTTPRequestHandler, directory=temporary))
    server.timeout = 1
    deadline = monotonic() + 120
    try:
        while monotonic() < deadline:
            server.handle_request()
    finally:
        server.server_close()
