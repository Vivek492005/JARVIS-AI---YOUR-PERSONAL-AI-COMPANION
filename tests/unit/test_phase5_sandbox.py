"""Tests for Phase 5.10 agent sandbox / isolation."""

import sys

import pytest

sys.path.insert(0, "src")

from jarvis.perception.sandbox import (  # noqa: E402
    ContainerSpec,
    SandboxLevel,
    assert_skill_allowed,
    build_container_spec,
    check_skill_allowed,
    current_level,
    docker_available,
    level_c_guide,
    min_level_for_trust,
    run_in_container,
    to_docker_args,
)
from jarvis.tools.registry import REGISTRY, Risk  # noqa: E402


def test_min_level_for_trust():
    assert min_level_for_trust("third_party") == SandboxLevel.B
    assert min_level_for_trust("local") == SandboxLevel.A


def test_check_skill_allowed_levels():
    ok, _ = check_skill_allowed("s", "local", SandboxLevel.A)
    assert ok
    ok, reason = check_skill_allowed("s", "third_party", SandboxLevel.A)
    assert not ok and "level B+" in reason
    ok, _ = check_skill_allowed("s", "third_party", SandboxLevel.B)
    assert ok
    ok, _ = check_skill_allowed("s", "third_party", SandboxLevel.C)
    assert ok


def test_current_level_defaults_a():
    assert current_level() == SandboxLevel.A


def test_assert_skill_allowed_raises():
    with pytest.raises(PermissionError):
        assert_skill_allowed("evil-skill", "third_party", SandboxLevel.A)
    assert_skill_allowed("evil-skill", "third_party", SandboxLevel.B)  # no raise


def test_build_container_spec_clamps_timeout():
    spec = build_container_spec(["python", "--version"], timeout_s=9999)
    assert spec.timeout_s == 600.0
    spec = build_container_spec(["x"], timeout_s=1)
    assert spec.timeout_s == 5.0
    with pytest.raises(ValueError):
        build_container_spec([])


def test_docker_args_locked_down(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_WORKSPACE", str(tmp_path))
    spec = build_container_spec(["python", "main.py"])
    args = to_docker_args(spec)
    assert "--network" in args and "none" in args
    assert "--cpus" in args and "--memory" in args
    # workspace mounted read-only
    ro = [a for a in args if "readonly" in a]
    assert len(ro) == 1 and str(tmp_path) in ro[0]
    # only out/ is writable
    assert any("dst=/out" in a for a in args)
    assert args[-2:] == ["python", "main.py"]


def test_run_in_container_no_docker(monkeypatch, tmp_path):
    monkeypatch.setenv("JARVIS_WORKSPACE", str(tmp_path))
    import jarvis.perception.sandbox as sb
    monkeypatch.setattr(sb, "docker_available", lambda: False)
    spec = build_container_spec(["echo", "hi"])
    out = run_in_container(spec)
    assert "docker not available" in out
    assert "NOT executed" in out


def test_level_c_guide_lists_steps():
    guide = level_c_guide()
    assert "jarvis-agent" in guide
    assert "Windows Sandbox" in guide


def test_tool_registered_system():
    assert REGISTRY["sandbox_exec"].risk == Risk.SYSTEM


def test_run_action_sandbox_exec_gated(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_WORKSPACE", str(tmp_path))
    from jarvis.tools.actions import run_action
    # SYSTEM tier at L1 -> confirm/deny, never silent allow
    verdict, _ = run_action("sandbox_exec", {"command": ["echo", "hi"]})
    assert verdict in ("confirm", "deny"), verdict


def test_skill_loader_hook(tmp_path):
    from jarvis.brain.skills.loader import load_skill
    from jarvis.brain.skills.trust import TrustLevel
    import textwrap

    d = tmp_path / "sk"
    d.mkdir()
    (d / "SKILL.md").write_text(textwrap.dedent("""\
        ---
        name: sk
        description: test skill
        ---
        # sk
        """))
    # third-party at default Level A -> refused
    with pytest.raises(PermissionError):
        load_skill(d, trust=TrustLevel.THIRD_PARTY)
    # local is fine
    load_skill(d, trust=TrustLevel.LOCAL)
