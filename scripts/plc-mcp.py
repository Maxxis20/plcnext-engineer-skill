#!/usr/bin/env python3
"""plc-mcp.py: talk to the MCP server app on a PLCnext controller without an MCP client (Phoenix Contact
"MCP for PLCnext Control", port 58080). Logs in like a client would (OAuth 2.0 with PKCE: dynamic client
registration, the server's login with the controller's user, code for token), then speaks MCP over Streamable
HTTP (JSON-RPC).

  plc-mcp.py tools                     list the tools (name and the first line of the description)
  plc-mcp.py schema <tool>             the tool's input schema
  plc-mcp.py call <tool> ['<json>']    call a tool with JSON arguments, print the result's text
  plc-mcp.py resources                 list the resources
  plc-mcp.py resource <uri>            read one resource (e.g. docs://plcnext/device/status/parameters)

Environment: PLC_HOST (address, default 192.168.1.10), PLC_USER (default admin), PLC_SECRET (NAME of the variable
holding the password, default PLC_PASSWORD; run it under your secret runner), PLC_MCP_CA (PEM of the controller's
HTTPS certificate; without it the certificate is not checked: test benches only). The password and the token are
never printed and never written to disk."""
import base64, hashlib, json, os, secrets, ssl, sys, urllib.parse, urllib.request

HOST = os.environ.get("PLC_HOST", "192.168.1.10")
BASE = f"https://{HOST}:58080"
CA = os.environ.get("PLC_MCP_CA")
CTX = ssl.create_default_context(cafile=CA) if CA else ssl._create_unverified_context()
REDIRECT = "http://127.0.0.1:8976/callback"          # never contacted: the code is taken from the login answer


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


OPEN = urllib.request.build_opener(urllib.request.HTTPSHandler(context=CTX), NoRedirect)


def http(method, path, body=None, headers=None, form=False):
    h = dict(headers or {})
    data = None
    if body is not None:
        if form:
            data = urllib.parse.urlencode(body).encode(); h["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            data = json.dumps(body).encode(); h["Content-Type"] = "application/json"
    req = urllib.request.Request(path if path.startswith("http") else BASE + path, data=data, headers=h, method=method)
    try:
        r = OPEN.open(req, timeout=60)
        return r.status, dict(r.headers), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode("utf-8", "replace")


def login():
    pw = os.environ.get(os.environ.get("PLC_SECRET", "PLC_PASSWORD"))
    if not pw:
        sys.exit("plc-mcp: no password in the variable named by PLC_SECRET (run under your secret runner)")
    s, _, b = http("POST", "/register", {"client_name": "plc-mcp.py", "redirect_uris": [REDIRECT],
                                          "grant_types": ["authorization_code"], "response_types": ["code"],
                                          "token_endpoint_auth_method": "client_secret_post"})
    if s not in (200, 201):
        sys.exit(f"plc-mcp: register failed ({s}): {b[:200]}")
    cl = json.loads(b)
    ver = secrets.token_urlsafe(48)
    chal = base64.urlsafe_b64encode(hashlib.sha256(ver.encode()).digest()).rstrip(b"=").decode()
    q = urllib.parse.urlencode({"response_type": "code", "client_id": cl["client_id"], "redirect_uri": REDIRECT,
                                "code_challenge": chal, "code_challenge_method": "S256", "state": "x"})
    s, h, b = http("GET", "/authorize?" + q)
    loc = h.get("Location") or h.get("location") or ""
    sess = urllib.parse.parse_qs(urllib.parse.urlparse(loc).query).get("auth_session", [""])[0]
    if not sess:
        sys.exit(f"plc-mcp: authorize gave no login session ({s})")
    s, h, b = http("POST", "/auth/login?auth_session=" + urllib.parse.quote(sess),
                   {"username": os.environ.get("PLC_USER", "admin"), "password": pw})
    pw = None
    if s != 200:
        sys.exit(f"plc-mcp: login refused ({s}): {b[:200]}")
    target = json.loads(b).get("redirect", "")
    if "code=" not in target:                     # a consent/warning step: follow the redirect once
        s, h, b = http("GET", target)
        target = h.get("Location") or h.get("location") or ""
    code = urllib.parse.parse_qs(urllib.parse.urlparse(target).query).get("code", [""])[0]
    if not code:
        sys.exit("plc-mcp: no authorization code after the login")
    tok = {"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT, "code_verifier": ver,
           "client_id": cl["client_id"]}
    if cl.get("client_secret"):
        tok["client_secret"] = cl["client_secret"]
    s, _, b = http("POST", "/token", tok, form=True)
    if s != 200:
        sys.exit(f"plc-mcp: token refused ({s}): {b[:200]}")
    return json.loads(b)["access_token"]


class Mcp:
    def __init__(self, token):
        self.h = {"Authorization": "Bearer " + token, "Accept": "application/json, text/event-stream"}
        self.n = 0
        r = self.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                    "clientInfo": {"name": "plc-mcp.py", "version": "1"}})
        self.info = r.get("result", {})
        self.notify("notifications/initialized")

    def _post(self, msg):
        s, h, b = http("POST", "/mcp", msg, self.h)
        sid = h.get("Mcp-Session-Id") or h.get("mcp-session-id")
        if sid:
            self.h["Mcp-Session-Id"] = sid
        if s >= 400:
            sys.exit(f"plc-mcp: MCP error {s}: {b[:300]}")
        if b.lstrip().startswith("{"):
            return json.loads(b)
        for line in b.splitlines():                      # text/event-stream: take the last data line
            if line.startswith("data:"):
                last = line[5:].strip()
        return json.loads(last) if b.strip() else {}

    def rpc(self, method, params=None):
        self.n += 1
        return self._post({"jsonrpc": "2.0", "id": self.n, "method": method, "params": params or {}})

    def notify(self, method):
        http("POST", "/mcp", {"jsonrpc": "2.0", "method": method}, self.h)


def main(a):
    if not a or a[0] not in ("tools", "schema", "call", "resources", "resource"):
        sys.exit(__doc__)
    m = Mcp(login())
    if a[0] == "tools":
        r = m.rpc("tools/list")
        for t in r.get("result", {}).get("tools", []):
            print(f"{t['name']:40s} {(t.get('description') or '').strip().splitlines()[0][:110] if t.get('description') else ''}")
    elif a[0] == "schema":
        for t in m.rpc("tools/list").get("result", {}).get("tools", []):
            if t["name"] == a[1]:
                print(t.get("description", "")); print(json.dumps(t.get("inputSchema", {}), indent=1))
    elif a[0] == "resource":
        for c in m.rpc("resources/read", {"uri": a[1]}).get("result", {}).get("contents", []):
            print(c.get("text", json.dumps(c)))
    elif a[0] == "resources":
        print(json.dumps(m.rpc("resources/list").get("result", {}), indent=1)[:4000])
    else:
        r = m.rpc("tools/call", {"name": a[1], "arguments": json.loads(a[2]) if len(a) > 2 else {}})
        if "error" in r:
            print("ERROR", json.dumps(r["error"])); return 1
        res = r.get("result", {})
        for c in res.get("content", []):
            print(c.get("text", json.dumps(c)))
        if res.get("isError"):
            return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
