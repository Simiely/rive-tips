"""Minimal MCP client for the Rive desktop app (127.0.0.1:9791).

Usage:
    python rive_mcp.py <tool> [args-json-file-or-inline]
    python rive_mcp.py capture_artboard '{"artboardId":"0-1","longEdge":1024}' --out shot.png
"""
import json
import sys
import urllib.request

ENDPOINT = "http://127.0.0.1:9791/mcp"


def _post(body, session_id=None, timeout=180):
    data = json.dumps(body).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    req = urllib.request.Request(ENDPOINT, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return resp.headers.get("Mcp-Session-Id"), raw


def _parse(raw):
    lines = [l[5:].strip() for l in raw.splitlines() if l.startswith("data:")]
    payload = "".join(lines) if lines else raw
    return json.loads(payload)


def connect():
    sid, raw = _post({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "rive-mcp-py", "version": "1.0"},
        },
    })
    _post({"jsonrpc": "2.0", "method": "notifications/initialized"}, sid)
    return sid


def call(tool, args=None, sid=None, timeout=180):
    if sid is None:
        sid = connect()
    result = _post({
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": tool, "arguments": args or {}},
    }, sid, timeout)
    return _parse(result[1])


def text_of(res):
    if "error" in res:
        return "MCP_ERROR: " + json.dumps(res["error"], ensure_ascii=False)
    out = []
    for item in res.get("result", {}).get("content", []):
        if item.get("type") == "text":
            out.append(item["text"])
        elif item.get("type") == "image":
            out.append("IMAGE_BASE64_LEN: %d" % len(item["data"]))
    return "\n".join(out)


def call_text(tool, args=None, sid=None):
    return text_of(call(tool, args, sid))


if __name__ == "__main__":
    tool = sys.argv[1]
    args = {}
    out_path = None
    rest = sys.argv[2:]
    if "--out" in rest:
        i = rest.index("--out")
        out_path = rest[i + 1]
        rest = rest[:i] + rest[i + 2:]
    if rest:
        spec = rest[0]
        if spec.strip().startswith("{"):
            args = json.loads(spec)
        else:
            with open(spec, encoding="utf-8-sig") as f:
                args = json.load(f)
    res = call(tool, args)
    if out_path:
        for item in res.get("result", {}).get("content", []):
            if item.get("type") == "image":
                import base64
                with open(out_path, "wb") as f:
                    f.write(base64.b64decode(item["data"]))
                print("IMAGE_SAVED: " + out_path)
    print(text_of(res))
