"""Tests for the control center API (Task 7.7)."""

import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, "src")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from jarvis.server.control import build_control_router, _redact_settings


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # service WITHOUT a pre-created MemoryStore: control._memory_store
    # creates one per request from memory_workspace, which keeps each
    # sqlite connection on its own request thread.
    svc = SimpleNamespace(
        agent=SimpleNamespace(model_router=None, cost_guard=None),
    )
    import jarvis.core.config as cfgmod
    monkeypatch.setattr(cfgmod.get_settings().brain, "memory_workspace", str(tmp_path))
    monkeypatch.setenv("JARVIS_TOKEN", "test-token")

    def verify():
        return None

    app = FastAPI()
    app.include_router(build_control_router(svc, verify))
    return TestClient(app)


def test_settings_redacts_secrets():
    s = SimpleNamespace(
        voice={"neural_voice": "x"},
        brain={"huggingface_api_key": "sk-secret", "daily_token_budget": 0},
        safety={"autonomy_level": 1},
        privacy={"privacy_mode": False},
        model_dump=lambda: {"voice": s.voice, "brain": s.brain,
                            "safety": s.safety, "privacy": s.privacy},
    )
    out = _redact_settings(s)
    assert out["brain"]["huggingface_api_key"] == "***REDACTED***"
    assert out["brain"]["daily_token_budget"] == 0


def test_get_settings_ok(client):
    r = client.get("/api/settings")
    assert r.status_code == 200
    body = r.json()
    assert set(body) >= {"voice", "brain", "safety", "privacy"}


def test_put_settings_allowlisted(client):
    r = client.put("/api/settings",
                   json={"updates": {"safety.autonomy_level": 2}})
    assert r.status_code == 200
    assert r.json()["applied"] == ["safety.autonomy_level"]


def test_put_settings_rejects_unknown(client):
    r = client.put("/api/settings",
                   json={"updates": {"brain.huggingface_api_key": "evil"}})
    assert r.json()["rejected"] == ["brain.huggingface_api_key"]


def test_put_settings_rejects_bad_range(client):
    r = client.put("/api/settings",
                   json={"updates": {"safety.autonomy_level": 99}})
    assert r.json()["rejected"] == ["safety.autonomy_level"]


def test_memory_crud(client):
    r = client.post("/api/memory/facts",
                    json={"key": "dog", "value": "Tommy"})
    assert r.status_code == 200
    facts = client.get("/api/memory/facts").json()
    assert any(f["key"] == "dog" and f["value"] == "Tommy" for f in facts)
    fid = next(f["id"] for f in facts if f["key"] == "dog")
    assert client.delete(f"/api/memory/facts/{fid}").status_code == 200
    assert client.delete("/api/memory/facts/999999").status_code == 404


def test_audit_endpoints(client):
    assert client.get("/api/audit?limit=5").status_code == 200
    stats = client.get("/api/audit/stats").json()
    assert "entries" in stats


def test_providers_and_costs_degrade_gracefully(client):
    assert client.get("/api/providers").status_code == 200
    costs = client.get("/api/costs").json()
    assert costs["note"] == "cost tracking not attached"


def test_skills_enable_disable(tmp_path, monkeypatch):
    from jarvis.core.config import get_settings
    skills_dir = tmp_path / "skills"
    (skills_dir / "demo").mkdir(parents=True)
    (skills_dir / "demo" / "SKILL.md").write_text(
        "---\nname: demo\nversion: 1.0.0\ndescription: test\n---\n", encoding="utf-8")

    # Point the settings at our fake skills dir.
    from jarvis.server import control as ctrl
    orig_flag = ctrl._skill_flag

    def fake_flag(name, enable):
        flag = skills_dir / name / ".disabled"
        if enable:
            flag.unlink(missing_ok=True)
        else:
            flag.touch()

    monkeypatch.setattr(ctrl, "_skill_flag", fake_flag)
    monkeypatch.setattr("jarvis.brain.skills.load_manifest",
                        lambda p: SimpleNamespace(
                            name="demo", version="1.0.0",
                            description="test",
                            trust=SimpleNamespace(value="local"),
                            tools=[], permissions=["shell"]))

    import jarvis.core.config as cfgmod
    monkeypatch.setattr(cfgmod.get_settings().brain, "skills_dir", str(skills_dir))

    def verify():
        return None
    app = FastAPI()
    app.include_router(build_control_router(SimpleNamespace(), verify))
    c = TestClient(app)
    assert c.post("/api/skills/demo/disable").status_code == 200
    assert (skills_dir / "demo" / ".disabled").exists()
    assert c.post("/api/skills/demo/enable").status_code == 200
    assert not (skills_dir / "demo" / ".disabled").exists()
