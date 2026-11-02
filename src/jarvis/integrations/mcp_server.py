"""JARVIS as an MCP server (Master Plan Task 6.2).

Exposes JARVIS's safe tools (READ and REVERSIBLE tiers only) over the MCP
stdio protocol, so Claude Desktop / IDE agents can use them. Every tool
call goes through :func:`run_action` — the same policy engine, the same
audit log.

Auth: the server requires ``JARVIS_MCP_TOKEN`` to be set in its
environment, and the client must pass the same token in the
``initialize`` params as ``{"token": "..."}``. Mismatch (or missing
token on either side) → the server refuses to initialize. This is the
stdio analogue of the plan's "localhost + token" requirement: whoever
can spawn this process on the machine must still prove the token.

Only READ/REVERSIBLE tools are listed. DESTRUCTIVE/SYSTEM tools are
never exposed, even if the policy engine would allow them — an external
agent must not be one prompt-injection away from ``empty_recycle_bin``.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional

from jarvis.tools.registry import REGISTRY, Risk

logger = logging.getLogger(__name__)

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "jarvis"
SERVER_VERSION = "0.8.0"

# Tiers an external MCP client may invoke. DESTRUCTIVE/SYSTEM are never
# listed, regardless of policy verdicts.
EXPOSED_TIERS = frozenset({Risk.READ, Risk.REVERSIBLE})


class AuthError(RuntimeError):
    pass


def _expected_token() -> str:
    return os.getenv("JARVIS_MCP_TOKEN", "")


def check_token(provided: Optional[str]) -> None:
    """Raise AuthError unless the token matches the server-side secret."""
    expected = _expected_token()
    if not expected:
        raise AuthError("server has no JARVIS_MCP_TOKEN configured")
    if not provided or provided != expected:
        raise AuthError("bad MCP token")


def exposed_tools() -> List[Dict[str, Any]]:
    """Tool descriptors for tools/list: READ/REVERSIBLE only.

    Dotted sub-specs (e.g. ``uia_invoke.destructive``) are never listed
    directly; base names are resolved with empty args so the tier check
    uses the same fail-closed resolution the gate applies.
    """
    from jarvis.tools.registry import resolve
    seen = set()
    tools = []
    for name in REGISTRY:
        if "." in name or name in seen:
            continue
        seen.add(name)
        spec = resolve(name, {})
        if spec is None or spec.risk not in EXPOSED_TIERS:
            continue
        try:
            schema = spec.params.model_json_schema()
        except Exception:
            schema = {"type": "object"}
        tools.append({
            "name": name,
            "description": spec.description,
            "inputSchema": schema,
        })
    return sorted(tools, key=lambda t: t["name"])


def call_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute via the policy gate. Returns an MCP result dict."""
    from jarvis.tools.actions import run_action
    verdict, result = run_action(name, arguments or {})
    if verdict == "deny":
        return {"content": [{"type": "text", "text": result}],
                "isError": True}
    if verdict == "confirm":
        # An external client cannot answer our confirmation prompt, so a
        # CONFIRM verdict is a refusal, not a question.
        return {"content": [{"type": "text",
                             "text": "REFUSED: this tool needs interactive "
                                     "confirmation, which MCP clients cannot "
                                     "provide."}],
                "isError": True}
    return {"content": [{"type": "text", "text": result}]}


def handle(msg: Dict[str, Any], authed: List[bool]) -> Any:
    method = msg.get("method")
    mid = msg.get("id")
    params = msg.get("params", {}) or {}

    if method == "initialize":
        try:
            check_token(params.get("token"))
        except AuthError as e:
            if mid is not None:
                return {"jsonrpc": "2.0", "id": mid,
                        "error": {"code": -32000, "message": str(e)}}
            return None
        authed.append(True)
        return {"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        }}

    if not authed:
        if mid is not None:
            return {"jsonrpc": "2.0", "id": mid,
                    "error": {"code": -32000,
                              "message": "not authenticated: call initialize with a token first"}}
        return None

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid,
                "result": {"tools": exposed_tools()}}
    if method == "tools/call":
        name = params.get("name", "")
        if name not in REGISTRY or not any(
                t["name"] == name for t in exposed_tools()):
            return {"jsonrpc": "2.0", "id": mid, "result": {
                "isError": True,
                "content": [{"type": "text",
                             "text": f"tool not exposed: {name}"}]}}
        return {"jsonrpc": "2.0", "id": mid,
                "result": call_tool(name, params.get("arguments") or {})}
    if mid is not None:
        return {"jsonrpc": "2.0", "id": mid,
                "error": {"code": -32601, "message": "Method not found"}}
    return None


def main() -> None:
    # Register every ToolSpec (base + perception + integrations) so the
    # policy gate sees the full surface.
    from jarvis.tools.actions import _register_tools
    _register_tools()
    authed: List[bool] = []
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        reply = handle(msg, authed)
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
