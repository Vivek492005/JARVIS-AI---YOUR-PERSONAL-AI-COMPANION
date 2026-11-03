"""Tests for the .jskill package format and Ed25519 signing.

All keys are generated fresh per-test (never committed, never on disk
outside tmp dirs). ``tool.py`` payloads contain tripwires proving the
package code is never executed during build/verify/install.
"""

import json
import zipfile
from pathlib import Path

import pytest

from jarvis.marketplace import ed25519
from jarvis.marketplace.package import (
    MANIFEST_NAME, PackageError, build_package, canonical_bytes,
    load_package, pack_zip, validate_manifest_schema,
)
from jarvis.marketplace.signing import (
    CuratorStore, sign_package, verify_package,
)

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

# If this file is ever imported/executed, the tripwire fires.
TOOL_PY = 'raise RuntimeError("TRIPWIRE: package code was executed!")\n'


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
    (d / "data.txt").write_text("hello\n", encoding="utf-8")
    return d


@pytest.fixture()
def signed_pkg_dir(tmp_path, skill_dir, author):
    staging = build_package(skill_dir, author="tester",
                            author_key_id=author["key_id"],
                            min_jarvis="0.1.0")
    sign_package(staging, author["seed"])
    return staging


def test_build_sign_verify_roundtrip(signed_pkg_dir, author):
    res = verify_package(signed_pkg_dir)
    assert res.ok, res.errors
    assert res.trust == "self-signed"
    assert res.key_id == author["key_id"]
    assert res.name == "demo-skill" and res.version == "1.2.0"


def test_pack_zip_roundtrip(tmp_path, signed_pkg_dir):
    zpath = pack_zip(signed_pkg_dir, tmp_path / "demo-skill-1.2.0.jskill")
    assert zpath.exists()
    res = verify_package(zpath)
    assert res.ok, res.errors
    assert res.trust == "self-signed"


def test_unsigned_package_refused(skill_dir, author):
    staging = build_package(skill_dir, author="tester",
                            author_key_id=author["key_id"],
                            min_jarvis="0.1.0")
    res = verify_package(staging)
    assert not res.ok
    assert any("SIGNATURE" in e for e in res.errors)


def test_tampered_file_refused(signed_pkg_dir):
    (signed_pkg_dir / "data.txt").write_text("evil\n", encoding="utf-8")
    res = verify_package(signed_pkg_dir)
    assert not res.ok
    assert any("hash mismatch" in e for e in res.errors)


def test_tampered_manifest_refused(signed_pkg_dir):
    man_path = signed_pkg_dir / MANIFEST_NAME
    man = json.loads(man_path.read_text(encoding="utf-8"))
    man["version"] = "9.9.9"
    man_path.write_text(json.dumps(man), encoding="utf-8")
    res = verify_package(signed_pkg_dir)
    assert not res.ok
    assert any("signature" in e.lower() for e in res.errors)


def test_extra_unpinned_file_refused(signed_pkg_dir):
    (signed_pkg_dir / "smuggled.py").write_text("evil", encoding="utf-8")
    res = verify_package(signed_pkg_dir)
    assert not res.ok
    assert any("unpinned" in e for e in res.errors)


def test_missing_pinned_file_refused(signed_pkg_dir):
    (signed_pkg_dir / "data.txt").unlink()
    res = verify_package(signed_pkg_dir)
    assert not res.ok
    assert any("missing" in e for e in res.errors)


def test_wrong_key_refused(signed_pkg_dir):
    other_seed, _ = ed25519.keypair()
    sig_path = signed_pkg_dir / "SIGNATURE.json"
    sig = json.loads(sig_path.read_text(encoding="utf-8"))
    # Re-sign the manifest bytes with a different key but keep key_id.
    from jarvis.marketplace.package import canonical_bytes as cb
    man = json.loads((signed_pkg_dir / MANIFEST_NAME).read_text(
        encoding="utf-8"))
    sig["signature"] = ed25519.sign(other_seed, cb(man)).hex()
    sig_path.write_text(json.dumps(sig), encoding="utf-8")
    res = verify_package(signed_pkg_dir)
    assert not res.ok


def test_skill_md_permissions_must_match_manifest(tmp_path, skill_dir, author):
    # Attack: manifest declares narrow permissions up front, but SKILL.md
    # (correctly hashed) requests broad ones at runtime.
    staging = build_package(skill_dir, author="tester",
                            author_key_id=author["key_id"],
                            min_jarvis="0.1.0")
    man_path = staging / "MANIFEST.json"
    man = json.loads(man_path.read_text(encoding="utf-8"))
    man["permissions"] = []  # lie up front
    man_path.write_text(json.dumps(man, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
    sign_package(staging, author["seed"])
    res = verify_package(staging)
    assert not res.ok
    assert any("permissions" in e for e in res.errors)


def test_schema_rejects_unknown_fields():
    with pytest.raises(PackageError, match="unknown manifest fields"):
        validate_manifest_schema({
            "format": "jarvis-skill-package/1", "name": "x", "version": "1.0.0",
            "author": "a", "author_key_id": "0" * 16, "min_jarvis": "0.1.0",
            "permissions": [], "files": {"SKILL.md": "0" * 64},
            "evil": "field"})


def test_schema_rejects_bad_name_and_version():
    base = {"format": "jarvis-skill-package/1", "name": "ok-name",
            "version": "1.0.0", "author": "a", "author_key_id": "0" * 16,
            "min_jarvis": "0.1.0", "permissions": [],
            "files": {"SKILL.md": "0" * 64}}
    for bad in ("../evil", "UPPER", "has space", ""):
        with pytest.raises(PackageError):
            validate_manifest_schema({**base, "name": bad})
    for bad in ("1.0", "v1.0.0", "1.0.0.0", ""):
        with pytest.raises(PackageError):
            validate_manifest_schema({**base, "version": bad})


def test_zip_slip_refused(tmp_path):
    zpath = tmp_path / "evil.jskill"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("../../evil.txt", "pwned")
        zf.writestr(MANIFEST_NAME, "{}")
    with pytest.raises(PackageError, match="unsafe zip member"):
        load_package(zpath)


def test_canonical_bytes_deterministic():
    obj = {"b": 1, "a": [3, 2]}
    assert canonical_bytes(obj) == b'{"a":[3,2],"b":1}'


def test_curator_tier_when_key_trusted(tmp_path, signed_pkg_dir, author,
                                       monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    store = CuratorStore()
    store.add(author["pub"].hex(), name="tester")
    res = verify_package(signed_pkg_dir, curators=store)
    assert res.ok, res.errors
    assert res.trust == "curator"


def test_curator_store_rejects_bad_key(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    store = CuratorStore()
    with pytest.raises(PackageError):
        store.add("not-hex")
    with pytest.raises(PackageError):
        store.add("00" * 10)  # wrong length
    assert store.list() == []


def test_sign_refuses_key_id_mismatch(skill_dir, author):
    other_seed, _ = ed25519.keypair()
    staging = build_package(skill_dir, author="tester",
                            author_key_id=author["key_id"],
                            min_jarvis="0.1.0")
    with pytest.raises(PackageError, match="does not match"):
        sign_package(staging, other_seed)


def test_double_sign_refused(signed_pkg_dir, author):
    with pytest.raises(PackageError, match="already signed"):
        sign_package(signed_pkg_dir, author["seed"])


def test_pack_refuses_unsigned(tmp_path, skill_dir, author):
    staging = build_package(skill_dir, author="tester",
                            author_key_id=author["key_id"],
                            min_jarvis="0.1.0")
    with pytest.raises(PackageError, match="unsigned"):
        pack_zip(staging, tmp_path / "x.jskill")


def test_load_package_missing_file(tmp_path):
    with pytest.raises(PackageError, match="not found"):
        load_package(tmp_path / "nope.jskill")


def test_tripwire_tool_py_never_executed(tmp_path, signed_pkg_dir):
    # The tripwire raises RuntimeError at import; verify_package and the
    # whole build pipeline must complete without importing it.
    marker = tmp_path / "tripwire-marker"
    assert not marker.exists()
    res = verify_package(signed_pkg_dir)
    assert res.ok
