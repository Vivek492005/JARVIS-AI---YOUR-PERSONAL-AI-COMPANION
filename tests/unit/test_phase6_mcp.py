"""Tests for Task 6.1 (MCP client) and 6.2 (JARVIS as MCP server)."""

import os
import sys

import pytest

from jarvis.integrations.mcp import (
    MCPClient, MCPError, MCPServerConfig, discover_tools, load_server_configs,
    register_mcp_tools, sanitize_description,
)
from jarvis.tools.registry import REGISTRY, Risk

REPO = "/home/hatch/workspace/jarvis-review"


def _fake_cfg(**kw):
    from tests.fakes.fake_mcp import server_command
    base = dict(name="fake", command=server_command())
    base.update(kw)
    return MCPServerConfig(**base)


def test_handshake_lists_and_calls(tmp_path=None):
    cfg = _fake_cfg()
    with MCPClient(cfg) as client:
        assert client.server_info.get("name") == "fake-mcp"
        tools = client.list_tools()
        names = [t["name"] for t in tools]
        assert "read_file" in names and "list_dir" in names
        out = client.call_tool("read_file", {"path": "/workspace/notes.md"})
        assert "hello world" in out
        err = client.call_tool("read_file", {"path": "/nope"})
        assert err.startswith("MCP_TOOL_ERROR:")


def test_unknown_server_never_autoconnects():
    cfg = MCPServerConfig(name="ghost")  # no command, no url
    with pytest.raises(MCPError):
        MCPClient(cfg).connect()


def test_remote_url_without_bridge_refused():
    cfg = MCPServerConfig(name="remote", url="https://example.com/mcp")
    with pytest.raises(MCPError):
        MCPClient(cfg).connect()


def test_discover_defaults_destructive_and_untrusted():
    cfg = _fake_cfg()
    with MCPClient(cfg) as client:
        specs = discover_tools(client)
    by_name = {s.name: s for s in specs}
    assert "mcp.fake.read_file" in by_name
    spec = by_name["mcp.fake.read_file"]
    assert spec.risk == Risk.DESTRUCTIVE          # deny-by-default
    assert spec.carries_external_data is True     # untrusted output
    assert spec.params.model_validate({"path": "/x"})
    with pytest.raises(ValueError):
        spec.params.model_validate({})            # required enforced
    with pytest.raises(ValueError):
        spec.params.model_validate({"path": "/x", "evil": 1})  # no extras


def test_risk_overrides_downgrade():
    cfg = _fake_cfg(risk_overrides={"read_file": "read"})
    with MCPClient(cfg) as client:
        specs = discover_tools(client)
    by_name = {s.name: s for s in specs}
    assert by_name["mcp.fake.read_file"].risk == Risk.READ
    assert by_name["mcp.fake.list_dir"].risk == Risk.DESTRUCTIVE


def test_unknown_risk_falls_back_destructive():
    cfg = _fake_cfg(risk_overrides={"read_file": "bogus"})
    with MCPClient(cfg) as client:
        specs = discover_tools(client)
    assert [s for s in specs
            if s.name == "mcp.fake.read_file"][0].risk == Risk.DESTRUCTIVE


def test_description_sanitized():
    # Fake server ships a poisoned description with a NUL byte.
    assert "\x00" not in sanitize_description("a\x00b")
    cfg = _fake_cfg()
    with MCPClient(cfg) as client:
        specs = discover_tools(client)
    desc = [s for s in specs if s.name == "mcp.fake.read_file"][0].description
    assert "\x00" not in desc


def test_load_server_configs(tmp_path):
    p = tmp_path / "mcp_servers.toml"
    p.write_text(
        '[servers.fs]\ncommand = ["npx", "-y", "x"]\n'
        'default_risk = "destructive"\n'
        '[servers.fs.risk_overrides]\nread = "read"\n'
        '[servers.bad]\ncommand = "not-a-list"\n'   # malformed -> skipped
        '[servers.off]\ncommand = ["y"]\nenabled = false\n')
    cfgs = load_server_configs(str(p))
    names = [c.name for c in cfgs]
    assert "fs" in names and "bad" not in names and "off" not in names
    fs = [c for c in cfgs if c.name == "fs"][0]
    assert fs.risk_overrides == {"read": "READ"}


def test_register_mcp_tools_idempotent():
    cfg = _fake_cfg(name="idem")
    with MCPClient(cfg) as client:
        specs = discover_tools(client)
    register_mcp_tools(specs)
    n1 = len(REGISTRY)
    register_mcp_tools(specs)
    assert len(REGISTRY) == n1
    assert "mcp.idem.read_file" in REGISTRY


# --- 6.2: JARVIS as MCP server -------------------------------------------

def _run_server_session(script, token="secret"):
    """Drive mcp_server.main() over pipes with a script of messages."""
    import subprocess
    import json
    env = dict(os.environ, JARVIS_MCP_TOKEN=token,
               PYTHONPATH=os.path.join(REPO, "src"))
    proc = subprocess.Popen(
        [sys.executable, "-c",
         "from jarvis.integrations.mcp_server import main; main()"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True, cwd=REPO, env=env)
    replies = []
    try:
        for msg in script:
            proc.stdin.write(json.dumps(msg) + "\n")
        proc.stdin.flush()
        for _ in script:
            line = proc.stdin and proc.stdout.readline()
            if not line:
                break
            replies.append(json.loads(line))
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        proc.terminate()
    return replies


def _init(token="secret"):
    return {"jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05",
                       "capabilities": {}, "clientInfo": {},
                       "token": token}}


def test_server_rejects_bad_token():
    replies = _run_server_session([_init("wrong")])
    assert replies and "error" in replies[0]


def test_server_requires_auth_before_tools():
    replies = _run_server_session([
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
    ])
    assert replies and "error" in replies[0]


def test_server_lists_only_safe_tiers():
    replies = _run_server_session([
        _init(),
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    ])
    tools = replies[1]["result"]["tools"]
    assert tools, "should expose some tools"
    # None of the exposed names may resolve to DESTRUCTIVE/SYSTEM.
    from jarvis.tools.registry import resolve
    for t in tools:
        spec = resolve(t["name"], {})
        assert spec is not None
        assert spec.risk in (Risk.READ, Risk.REVERSIBLE), t["name"]


def test_server_tool_call_goes_through_gate():
    replies = _run_server_session([
        _init(),
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
         "params": {"name": "tasks_list", "arguments": {}}},
    ])
    assert "result" in replies[1]
    assert not replies[1]["result"].get("isError")


def test_server_refuses_unexposed_tool():
    replies = _run_server_session([
        _init(),
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
         "params": {"name": "mail_send", "arguments": {}}},
    ])
    assert replies[1]["result"].get("isError")
