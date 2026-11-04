"""Tests for the install flow and revocation.

Fail-closed matrix: bad signature, hash mismatch, revoked key/package,
sandbox Level A, no confirmation, name collision — every one must refuse
without executing package code or writing to the skills dir.
"""

import json
from pathlib import Path

import pytest

from jarvis.brain.skills.trust import TrustLevel
from jarvis.marketplace import ed25519
from jarvis.marketplace.installer import (
    install_package,
    read_installed_record,
    trust_for_installed,
)
from jarvis.marketplace.package import build_package, pack_zip
from jarvis.marketplace.revocation import (
    RevocationList,
    load_local,
    save_local,
    sign_feed,
    update_from_feed,
)
from jarvis.marketplace.signing import CuratorStore, sign_package
from jarvis.perception.sandbox import SandboxLevel

SKILL_MD = """\
---
name: demo-skill
description: A demo skill for tests.
version: 1.2.0
permissions: [disk:notes]
tools:
  - {name: demo_tool, risk: reversible}
---
## Demo
Does demo things.
"""

TOOL_PY = 'raise RuntimeError("TRIPWIRE: package code was executed!")\n'


@pytest.fixture()
def home(tmp_path, monkeypatch):
    """Isolate ALL marketplace disk state (~/.jarvis/marketplace)."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return tmp_path


@pytest.fixture()
def author():
    seed, pub = ed25519.keypair()
    return {"seed": seed, "pub": pub, "key_id": ed25519.key_id(pub)}


@pytest.fixture()
def skill_dir(tmp_path):
    d = tmp_path / "demo-skill"
    d.mkdir()
    (d / "SKILL.md").write_text(SKILL_MD, encoding="utf-8")
    (d / "tool.py").write_text(TOOL_PY, encoding="utf-8")
    return d


@pytest.fixture()
def package_path(tmp_path, skill_dir, author):
    staging = build_package(
        skill_dir, author="tester", author_key_id=author["key_id"], min_jarvis="0.1.0"
    )
    sign_package(staging, author["seed"])
    return pack_zip(staging, tmp_path / "demo-skill-1.2.0.jskill")


@pytest.fixture()
def sandbox_b(monkeypatch):
    monkeypatch.setattr("jarvis.perception.sandbox.current_level", lambda: SandboxLevel.B)


@pytest.fixture()
def sandbox_a(monkeypatch):
    monkeypatch.setattr("jarvis.perception.sandbox.current_level", lambda: SandboxLevel.A)


@pytest.fixture()
def no_audit(monkeypatch):
    import jarvis.policy.audit as audit_mod

    monkeypatch.setattr(audit_mod, "AuditLogger", lambda *a, **k: _NullAudit())


class _NullAudit:
    def log(self, *a, **k):
        pass


def _install(pkg, skills_dir, **kw):
    kw.setdefault("confirm", lambda summary: True)
    return install_package(pkg, skills_dir, **kw)


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


def test_install_self_signed(home, package_path, tmp_path, sandbox_b, no_audit, author):
    skills = tmp_path / "skills"
    skills.mkdir()
    res = _install(package_path, skills)
    assert res.ok, res.errors
    assert res.trust == "self-signed"
    assert (skills / "demo-skill" / "SKILL.md").exists()
    assert (skills / "demo-skill" / "tool.py").exists()
    record = read_installed_record(skills / "demo-skill")
    assert record is not None
    assert record["key_id"] == author["key_id"]
    assert record["trust"] == "self-signed"
    # Tripwire: tool.py must be present but never executed.
    assert "TRIPWIRE" in (skills / "demo-skill" / "tool.py").read_text()


def test_install_curator_trust(home, package_path, tmp_path, sandbox_b, no_audit, author):
    store = CuratorStore()
    store.add(author["pub"].hex(), name="tester")
    skills = tmp_path / "skills"
    skills.mkdir()
    res = _install(package_path, skills, curators=store)
    assert res.ok, res.errors
    assert res.trust == "curator"
    assert read_installed_record(skills / "demo-skill")["trust"] == "curator"


def test_trust_for_installed_verified(home, package_path, tmp_path, sandbox_b, no_audit, author):
    store = CuratorStore()
    store.add(author["pub"].hex(), name="tester")
    skills = tmp_path / "skills"
    skills.mkdir()
    res = _install(package_path, skills, curators=store)
    assert res.ok
    assert trust_for_installed(skills / "demo-skill") == TrustLevel.VERIFIED


def test_trust_for_installed_self_signed(home, package_path, tmp_path, sandbox_b, no_audit):
    skills = tmp_path / "skills"
    skills.mkdir()
    res = _install(package_path, skills)
    assert res.ok
    assert trust_for_installed(skills / "demo-skill") == TrustLevel.THIRD_PARTY


def test_trust_downgrades_on_tamper(home, package_path, tmp_path, sandbox_b, no_audit):
    skills = tmp_path / "skills"
    skills.mkdir()
    res = _install(package_path, skills)
    assert res.ok
    (skills / "demo-skill" / "tool.py").write_text("# tampered\n")
    assert trust_for_installed(skills / "demo-skill") == TrustLevel.THIRD_PARTY


def test_trust_for_missing_record_is_third_party(tmp_path):
    d = tmp_path / "plain"
    d.mkdir()
    assert trust_for_installed(d) == TrustLevel.THIRD_PARTY


# ---------------------------------------------------------------------------
# Refusals (fail-closed)
# ---------------------------------------------------------------------------


def test_install_refused_at_sandbox_level_a(home, package_path, tmp_path, sandbox_a, no_audit):
    skills = tmp_path / "skills"
    skills.mkdir()
    res = _install(package_path, skills)
    assert not res.ok
    assert any("sandbox" in e.lower() or "level" in e.lower() for e in res.errors)
    assert not (skills / "demo-skill").exists()


def test_install_refused_without_confirmation(home, package_path, tmp_path, sandbox_b, no_audit):
    skills = tmp_path / "skills"
    skills.mkdir()
    res = install_package(package_path, skills, confirm=lambda summary: False)
    assert not res.ok
    assert any("confirm" in e.lower() for e in res.errors)
    assert not (skills / "demo-skill").exists()


def test_install_refused_on_name_collision(home, package_path, tmp_path, sandbox_b, no_audit):
    skills = tmp_path / "skills"
    skills.mkdir()
    assert _install(package_path, skills).ok
    res = _install(package_path, skills)
    assert not res.ok
    assert any("already installed" in e for e in res.errors)


def test_install_refused_on_tampered_sig(home, package_path, tmp_path, sandbox_b, no_audit):
    import zipfile

    evil = tmp_path / "evil.jskill"
    with zipfile.ZipFile(package_path) as zin, zipfile.ZipFile(evil, "w") as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename == "SIGNATURE.json":
                sig = json.loads(data)
                sig["signature"] = "00" * 64
                data = json.dumps(sig).encode()
            zout.writestr(info, data)
    skills = tmp_path / "skills"
    skills.mkdir()
    res = _install(evil, skills)
    assert not res.ok
    assert not (skills / "demo-skill").exists()


def test_install_never_executes_package_code(home, package_path, tmp_path, sandbox_b, no_audit):
    # tool.py raises at import; install must succeed regardless.
    skills = tmp_path / "skills"
    skills.mkdir()
    res = _install(package_path, skills)
    assert res.ok, res.errors


# ---------------------------------------------------------------------------
# Revocation
# ---------------------------------------------------------------------------


def test_revoked_key_refused(home, package_path, tmp_path, sandbox_b, no_audit, author):
    save_local(RevocationList(revoked_keys=[author["key_id"]]))
    skills = tmp_path / "skills"
    skills.mkdir()
    res = _install(package_path, skills)
    assert not res.ok
    assert any("revoked" in e for e in res.errors)


def test_revoked_package_refused(home, package_path, tmp_path, sandbox_b, no_audit):
    save_local(RevocationList(revoked_packages=["demo-skill@1.2.0"]))
    skills = tmp_path / "skills"
    skills.mkdir()
    res = _install(package_path, skills)
    assert not res.ok
    assert any("revoked" in e for e in res.errors)


def test_signed_feed_roundtrip(home, tmp_path):
    seed, pub = ed25519.keypair()
    feed = sign_feed(["deadbeefdeadbeef"], ["old-skill@0.1.0"], seed)
    feed_path = tmp_path / "feed.json"
    feed_path.write_text(json.dumps(feed), encoding="utf-8")
    merged = update_from_feed(feed_path, pub.hex())
    assert "deadbeefdeadbeef" in merged.revoked_keys
    assert "old-skill@0.1.0" in merged.revoked_packages
    # Cache is offline-readable.
    cached = load_local()
    assert cached.is_revoked("deadbeefdeadbeef", "x", "1.0.0") is not None
    assert cached.is_revoked("other", "old-skill", "0.1.0") is not None
    assert cached.is_revoked("other", "fine", "1.0.0") is None


def test_feed_with_bad_signature_rejected(home, tmp_path):
    seed, pub = ed25519.keypair()
    feed = sign_feed(["k1"], [], seed)
    feed["revoked_keys"] = ["tampered"]
    feed_path = tmp_path / "feed.json"
    feed_path.write_text(json.dumps(feed), encoding="utf-8")
    with pytest.raises(Exception, match="[Ss]ignature"):
        update_from_feed(feed_path, pub.hex())
    assert load_local().revoked_keys == []


def test_feed_from_wrong_curator_rejected(home, tmp_path):
    seed, _ = ed25519.keypair()
    _, other_pub = ed25519.keypair()
    feed = sign_feed(["k1"], [], seed)
    feed_path = tmp_path / "feed.json"
    feed_path.write_text(json.dumps(feed), encoding="utf-8")
    with pytest.raises(Exception, match="[Kk]ey"):
        update_from_feed(feed_path, other_pub.hex())


def test_revocation_cache_empty_by_default(home):
    rev = load_local()
    assert rev.revoked_keys == [] and rev.revoked_packages == []
