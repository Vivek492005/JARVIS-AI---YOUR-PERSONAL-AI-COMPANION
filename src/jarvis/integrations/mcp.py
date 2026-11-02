"""MCP client (Master Plan Task 6.1): talk to MCP servers as tool providers.

Design decision: instead of the official ``mcp`` Python SDK we implement
the small, stable subset of the MCP wire protocol we need (JSON-RPC 2.0
over stdio: ``initialize`` → ``notifications/initialized`` →
``tools/list`` → ``tools/call``). Rationale: zero new dependencies, fully
mockable for tests, and no SDK-version churn. The wire format is the
public MCP spec, so real servers (filesystem, GitHub, …) work unchanged.

Safety rules (from the plan):
* Servers come ONLY from an explicit allowlist (``mcp_servers.toml``).
  Unknown servers are never auto-connected.
* Discovered tools are wrapped as :class:`ToolSpec` with default risk
  **DESTRUCTIVE** (deny-by-default); ``risk_overrides`` in the config
  downgrade tool-by-tool after review.
* MCP tool outputs — and tool *descriptions* — are untrusted data
  (Task 1.5): results enter the prompt wrapped in ``<untrusted_data>``
  and descriptions are sanitized before display.
"""

from __future__ import annotations

import itertools
import json
import logging
import re
import subprocess
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, create_model

from jarvis.tools.registry import REGISTRY, Risk, ToolSpec, tool as _register

logger = logging.getLogger(__name__)

MCP_PROTOCOL_VERSION = "2024-11-05"
CLIENT_NAME = "jarvis"
CLIENT_VERSION = "0.8.0"

# Control characters (except \t \n) have no business in a tool description
# and are a classic prompt-injection hiding spot.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_description(text: str) -> str:
    """Strip control chars from an untrusted MCP tool description."""
    return _CONTROL_CHARS.sub("", text or "")[:2000]


# ---------------------------------------------------------------------------
# Server config
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MCPServerConfig:
    name: str
    command: List[str] = field(default_factory=list)   # stdio server
    url: str = ""                                        # remote (SSE/HTTP)
    default_risk: str = "DESTRUCTIVE"
    risk_overrides: Dict[str, str] = field(default_factory=dict)
    version_pin: str = ""  # e.g. "@modelcontextprotocol/server-filesystem@1.2.3"
    enabled: bool = True


def load_server_configs(path: str) -> List[MCPServerConfig]:
    """Parse ``mcp_servers.toml``. Unknown/malformed entries are skipped."""
    import tomllib
    with open(path, "rb") as f:
        data = tomllib.load(f)
    configs: List[MCPServerConfig] = []
    for name, entry in (data.get("servers") or {}).items():
        try:
            command = entry.get("command", []) or []
            if not isinstance(command, list) or not all(
                    isinstance(x, str) for x in command):
                raise ValueError("command must be a list of strings")
            configs.append(MCPServerConfig(
                name=name,
                command=list(command),
                url=str(entry.get("url", "") or ""),
                default_risk=str(entry.get("default_risk", "DESTRUCTIVE") or "DESTRUCTIVE").upper(),
                risk_overrides={k: str(v).upper()
                              for k, v in (entry.get("risk_overrides")
                                            or {}).items()},
                version_pin=str(entry.get("version_pin", "") or ""),
                enabled=bool(entry.get("enabled", True)),
            ))
        except Exception as e:  # malformed entry: skip, don't crash
            logger.warning(f"Skipping malformed MCP server entry {name!r}: {e}")
    return [c for c in configs if c.enabled]


# ---------------------------------------------------------------------------
# Minimal MCP JSON-RPC client over stdio
# ---------------------------------------------------------------------------

class MCPError(RuntimeError):
    pass


class MCPClient:
    """One connected MCP server (stdio transport). Not thread-safe; guard
    with a lock if shared. Use as a context manager."""

    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._proc: Optional[subprocess.Popen] = None
        self._id = itertools.count(1)
        self._lock = threading.Lock()
        self.server_info: Dict[str, Any] = {}

    # -- lifecycle ------------------------------------------------------
    def connect(self, timeout_s: float = 10.0) -> None:
        if self._proc is not None:
            return
        if self.config.url and not self.config.command:
            raise MCPError("remote (URL) MCP servers need an explicit "
                           "bridge; configure a stdio command instead")
        if not self.config.command:
            raise MCPError(f"server {self.config.name!r} has no command")
        # S603: command comes from the admin-written allowlist config
        # (mcp_servers.toml), never from user/LLM input.
        self._proc = subprocess.Popen(  # noqa: S603
            self.config.command,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1,
        )
        try:
            result = self._request("initialize", {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": CLIENT_NAME, "version": CLIENT_VERSION},
            }, timeout_s=timeout_s)
            self.server_info = result.get("serverInfo", {})
            self._notify("notifications/initialized", {})
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        proc, self._proc = self._proc, None
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception as e:
                    logger.debug(f"mcp server {self.config.name!r} kill "
                                 f"failed: {e}")

    def __enter__(self) -> "MCPClient":
        self.connect()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # -- protocol -------------------------------------------------------
    def _request(self, method: str, params: Dict[str, Any],
                 timeout_s: float = 10.0) -> Dict[str, Any]:
        assert self._proc and self._proc.stdin and self._proc.stdout
        rid = next(self._id)
        payload = json.dumps({"jsonrpc": "2.0", "id": rid,
                              "method": method, "params": params})
        with self._lock:
            try:
                self._proc.stdin.write(payload + "\n")
                self._proc.stdin.flush()
            except BrokenPipeError as e:
                raise MCPError(f"server {self.config.name!r} closed stdin") from e
            line = self._proc.stdout.readline()
        if not line:
            raise MCPError(f"server {self.config.name!r} closed stdout")
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            raise MCPError(f"bad JSON from {self.config.name!r}") from e
        if msg.get("id") != rid:
            raise MCPError(f"response id mismatch from {self.config.name!r}")
        if "error" in msg:
            err = msg["error"]
            raise MCPError(f"{self.config.name!r}: {err.get('message', err)}")
        return msg.get("result", {})

    def _notify(self, method: str, params: Dict[str, Any]) -> None:
        assert self._proc and self._proc.stdin
        payload = json.dumps({"jsonrpc": "2.0", "method": method,
                              "params": params})
        with self._lock:
            self._proc.stdin.write(payload + "\n")
            self._proc.stdin.flush()

    def list_tools(self) -> List[Dict[str, Any]]:
        result = self._request("tools/list", {})
        return result.get("tools", [])

    def call_tool(self, name: str, arguments: Dict[str, Any],
                  timeout_s: float = 30.0) -> str:
        """Call a tool. Returns concatenated text content.

        Raises MCPError on protocol errors; a tool-level error
        (``isError: true``) is returned as text prefixed with
        ``MCP_TOOL_ERROR:`` so the policy layer can see it.
        """
        result = self._request("tools/call",
                               {"name": name, "arguments": arguments or {}},
                               timeout_s=timeout_s)
        parts = []
        for block in result.get("content", []):
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            else:
                parts.append(json.dumps(block))
        text = "\n".join(parts)
        if result.get("isError"):
            return "MCP_TOOL_ERROR: " + text
        return text


# ---------------------------------------------------------------------------
# Discovery -> ToolSpec wrapping
# ---------------------------------------------------------------------------

_JSON_TYPE_MAP = {
    "string": str, "integer": int, "number": float,
    "boolean": bool, "array": list, "object": dict,
}


def _params_model(tool_name: str, schema: Dict[str, Any]) -> type[BaseModel]:
    """Build a pydantic params model from a JSON-Schema-ish inputSchema."""
    properties = (schema or {}).get("properties", {}) or {}
    required = set((schema or {}).get("required", []) or [])
    fields: Dict[str, Any] = {}
    for pname, pspec in properties.items():
        ptype = _JSON_TYPE_MAP.get(str(pspec.get("type", "string")), str)
        default = ... if pname in required else None
        fields[pname] = (ptype, Field(default, description=str(pspec.get("description", ""))[:300]))
    # Extra args are forbidden: MCP servers must not receive surprise params.
    safe = re.sub(r"\W", "_", tool_name) or "tool"
    from pydantic import ConfigDict
    return create_model(f"MCP_{safe}_Params",
                        __config__=ConfigDict(extra="forbid"),
                        **fields)  # type: ignore[call-overload]


def _risk_for(cfg: MCPServerConfig, tool_name: str) -> Risk:
    name = cfg.risk_overrides.get(tool_name, cfg.default_risk).upper()
    try:
        return Risk[name]
    except KeyError:
        logger.warning(f"Unknown risk {name!r} for MCP tool {tool_name}; "
                       f"falling back to DESTRUCTIVE")
        return Risk.DESTRUCTIVE


def discover_tools(client: MCPClient) -> List[ToolSpec]:
    """Wrap every tool of a connected server as a ToolSpec.

    Namespaced as ``mcp.<server>.<tool>``. Default risk DESTRUCTIVE
    (deny-by-default); outputs are untrusted (``carries_external_data``).
    """
    cfg = client.config
    specs: List[ToolSpec] = []
    for t in client.list_tools():
        tname = str(t.get("name", ""))
        if not tname:
            continue
        full_name = f"mcp.{cfg.name}.{tname}"
        description = sanitize_description(str(t.get("description", "")))
        model = _params_model(tname, t.get("inputSchema") or {})
        risk = _risk_for(cfg, tname)

        def _handler(args: Dict[str, Any], _ctx: Any = None,
                     _raw: str = "", _tname: str = tname,
                     _client: MCPClient = client) -> str:
            return _client.call_tool(_tname, args)

        spec = ToolSpec(
            name=full_name,
            description=f"[MCP:{cfg.name}] {description}",
            params=model,
            risk=risk,
            handler=_handler,
            timeout_s=30.0,
            scopes=frozenset({"mcp", cfg.name}),
            carries_external_data=True,   # Task 1.5: MCP output is untrusted
        )
        specs.append(spec)
    return specs


def register_mcp_tools(specs: List[ToolSpec]) -> None:
    """Idempotent registration of discovered MCP tools."""
    for spec in specs:
        if spec.name in REGISTRY:
            continue
        _register(spec)
