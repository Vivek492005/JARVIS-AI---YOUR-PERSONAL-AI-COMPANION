"""CLI smoke tests for the marketplace subcommands."""

import json
import stat
import sys
import types
from pathlib import Path

import pytest

from jarvis.cli import _cmd_skill
from jarvis.marketplace import ed25519

SKILL_MD = """\
---
name: demo-skill
description: A demo skill for tests.
version: 1.2.0
permissions: [disk:notes]
tools:
  - {name: demo_tool, risk: reversible}
---
"""


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return tmp_path


@pytest.fixture()
def author_key(tmp_path, home):
    seed, pub = ed25519.keypair()
    key_path = tmp_path / "author.key"
    key_path.write_text(seed.hex() + "\n", encoding="utf-8")
    return {"seed": seed, "pub": pub, "key_id": ed25519.key_id(pub),
            "path": key_path}


@pytest.fixture()
def skill_dir(tmp_path):
    d = tmp_path / "demo-skill"
    d.mkdir()
    (d / "SKILL.md").write_text(SKILL_MD, encoding="utf-8")
    (d / "tool.py").write_text("x = 1\n", encoding="utf-8")
    return d


@pytest.fixture()
def package_path(tmp_path, skill_dir, author_key, monkeypatch):
    monkeypatch.chdir(tmp_path)
    args = types.SimpleNamespace(skill_cmd="package", skill_arg=str(skill_dir),
                                 skill_extra=[str(author_key["path"]),
                                              "tester"])
    assert _cmd_skill(args) == 0
    zpath = tmp_path / "demo-skill-1.2.0.jskill"
    assert zpath.exists()
    return zpath


def _run(cmd, arg=None, extra=(), monkeypatch=None, skills_dir=None):
    if monkeypatch is not None and skills_dir is not None:
        monkeypatch.setattr("jarvis.cli._skills_dir", lambda: skills_dir)
    args = types.SimpleNamespace(skill_cmd=cmd, skill_arg=arg,
                                 skill_extra=list(extra))
    return _cmd_skill(args)


def test_verify_ok(home, package_path, tmp_path, monkeypatch):
    assert _run("verify", str(package_path)) == 0


def test_verify_bad_package(home, tmp_path):
    assert _run("verify", str(tmp_path / "nope.jskill")) == 1


def test_install_with_confirmation(home, package_path, tmp_path, monkeypatch):
    from jarvis.perception.sandbox import SandboxLevel
    monkeypatch.setattr("jarvis.perception.sandbox.current_level",
                        lambda: SandboxLevel.B)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: "haan")
    skills = tmp_path / "skills"
    skills.mkdir()
    assert _run("install", str(package_path), monkeypatch=monkeypatch,
                skills_dir=skills) == 0
    assert (skills / "demo-skill" / "SKILL.md").exists()


def test_install_declined(home, package_path, tmp_path, monkeypatch):
    from jarvis.perception.sandbox import SandboxLevel
    monkeypatch.setattr("jarvis.perception.sandbox.current_level",
                        lambda: SandboxLevel.B)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: "nahi")
    skills = tmp_path / "skills"
    skills.mkdir()
    assert _run("install", str(package_path), monkeypatch=monkeypatch,
                skills_dir=skills) == 1
    assert not (skills / "demo-skill").exists()


def test_keygen_creates_0600_key(home, tmp_path, monkeypatch):
    out = tmp_path / "my.key"
    assert _run("keygen", str(out)) == 0
    assert out.exists()
    mode = stat.S_IMODE(out.stat().st_mode)
    assert mode == 0o600, oct(mode)
    seed = bytes.fromhex(out.read_text(encoding="utf-8").strip())
    assert len(seed) == 32


def test_trust_add_list_remove(home, author_key):
    pubhex = author_key["pub"].hex()
    assert _run("trust", "add", (pubhex, "tester")) == 0
    assert _run("trust", "list") == 0
    assert _run("trust", "remove", (author_key["key_id"],)) == 0
    assert _run("trust", "list") == 0
    assert _run("trust", "remove", ("nope1234nope1234",)) == 1


def test_trust_add_bad_key(home):
    assert _run("trust", "add", ("zzzz",)) == 1


def test_package_needs_key(home, skill_dir):
    args = types.SimpleNamespace(skill_cmd="package",
                                 skill_arg=str(skill_dir), skill_extra=[])
    assert _cmd_skill(args) == 2


def test_update_revocations(home, tmp_path, author_key):
    from jarvis.marketplace.revocation import sign_feed
    feed = sign_feed(["deadbeefdeadbeef"], [], author_key["seed"])
    feed_path = tmp_path / "feed.json"
    feed_path.write_text(json.dumps(feed), encoding="utf-8")
    assert _run("update-revocations", str(feed_path),
                (author_key["pub"].hex(),)) == 0
    from jarvis.marketplace.revocation import load_local
    assert "deadbeefdeadbeef" in load_local().revoked_keys


def test_unknown_marketplace_cmd_falls_through(home):
    args = types.SimpleNamespace(skill_cmd="frobnicate", skill_arg=None,
                                 skill_extra=[])
    assert _cmd_skill(args) == 2
