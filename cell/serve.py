#!/usr/bin/env python3
"""Live borrow endpoint for the uniform-cell substrate (stdlib http.server).

Exposes a sibling's active Hom(-, X) over HTTP so a reachable machine can be queried without
importing anything. This is the live counterpart to delta-file sync: borrow when online,
replicate when not. Read-only; opens the db in mode=ro.

  GET /health          -> {"ok": true, "instance": "<bigbang-id>"}
  GET /hom?x=<cell id> -> {"hom": [{"i","j","b"}, ...]}   active cells touching X
"""
import http.server, socketserver, sqlite3, json, urllib.request, urllib.parse
from urllib.parse import urlparse, parse_qs

def make_handler(dbpath, instance_id=""):
    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def _json(self, obj, code=200):
            b = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers(); self.wfile.write(b)
        def do_GET(self):
            u = urlparse(self.path); q = parse_qs(u.query)
            if u.path == "/health":
                return self._json({"ok": True, "instance": instance_id})
            if u.path == "/hom":
                X = q.get("x", [None])[0]
                if not X: return self._json({"error": "missing x"}, 400)
                con = sqlite3.connect(f"file:{dbpath}?mode=ro", uri=True)
                rows = con.execute(
                    """SELECT c.i,c.j,c.b FROM cell c JOIN edge e ON e.cell=c.i
                       WHERE e.endpoint=? AND c.i IN (SELECT i FROM active) ORDER BY c.t""",
                    (X,)).fetchall()
                con.close()
                return self._json({"hom": [{"i": i, "j": json.loads(j), "b": b} for i, j, b in rows]})
            self._json({"error": "not found"}, 404)
    return H

def make_server(dbpath, port=0, instance_id=""):
    socketserver.TCPServer.allow_reuse_address = True
    return socketserver.TCPServer(("127.0.0.1", port), make_handler(dbpath, instance_id))

def borrow_http(base_url, X):
    """Client side: borrow active Hom(-, X) from a sibling's endpoint."""
    u = base_url.rstrip("/") + "/hom?x=" + urllib.parse.quote(X)
    with urllib.request.urlopen(u, timeout=5) as r:
        return json.loads(r.read().decode())["hom"]

if __name__ == "__main__":
    import sys
    dbpath = sys.argv[1]; port = int(sys.argv[2]) if len(sys.argv) > 2 else 8788
    srv = make_server(dbpath, port)
    print(f"serving Hom(-,X) for {dbpath} on http://127.0.0.1:{srv.server_address[1]}")
    srv.serve_forever()
