"""Tests for Task 8.4: auto-update client + portable builder + packaging lint."""
import hashlib
import json
import os

import pytest

from jarvis.core import updater

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))


class _FakeResp:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self, n=-1):
        data = self._payload[:n] if n != -1 else self._payload
        self._payload = self._payload[n:] if n != -1 else b""
        return data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _release_payload(tag="v1.0.0"):
    return json.dumps({
        "tag_name": tag,
        "assets": [
            {"name": f"JARVIS-Setup-{tag}.exe",
             "browser_download_url": "https://example.com/setup.exe"},
            {"name": "SHA256SUMS.txt",
             "browser_download_url": "https://example.com/SHA256SUMS.txt"},
        ],
    }).encode()


def test_check_for_update_newer(monkeypatch):
    monkeypatch.setattr(updater, "_get_json",
                        lambda url: json.loads(_release_payload()))
    info = updater.check_for_update("0.9.0")
    assert info is not None
    assert info.tag == "1.0.0"
    assert info.installer_url.endswith("setup.exe")


def test_check_for_update_current_is_none(monkeypatch):
    monkeypatch.setattr(updater, "_get_json",
                        lambda url: json.loads(_release_payload()))
    assert updater.check_for_update("1.0.0") is None


def test_check_for_update_network_failure_is_none(monkeypatch):
    def boom(url):
        raise OSError("no network")
    monkeypatch.setattr(updater, "_get_json", boom)
    assert updater.check_for_update("0.9.0") is None


def test_check_for_update_missing_assets(monkeypatch):
    payload = json.dumps({"tag_name": "v1.1.0", "assets": []}).encode()
    monkeypatch.setattr(updater, "_get_json",
                        lambda url: json.loads(payload))
    assert updater.check_for_update("0.9.0") is None


def test_https_only_rejects():
    with pytest.raises(ValueError):
        updater._https_only("http://example.com/x.exe")
    with pytest.raises(ValueError):
        updater._https_only("file:///etc/passwd")
    assert updater._https_only("https://example.com/x.exe")


def test_verify_sha256_ok_and_mismatch(tmp_path):
    f = tmp_path / "a.bin"
    f.write_bytes(b"hello")
    digest = hashlib.sha256(b"hello").hexdigest()
    sums = f"{digest}  a.bin\n"
    assert updater.verify_sha256(str(f), sums) is True
    assert updater.verify_sha256(str(f), "0" * 64 + "  a.bin\n") is False
    # missing entry = fail closed
    assert updater.verify_sha256(str(f), "deadbeef  other.bin\n") is False


def test_download_writes_file(monkeypatch, tmp_path):
    data = b"x" * 100
    monkeypatch.setattr(updater.urllib.request, "urlopen",
                        lambda req, timeout=None: _FakeResp(data))
    dest = str(tmp_path / "setup.exe")
    assert updater.download("https://example.com/setup.exe", dest) == dest
    assert open(dest, "rb").read() == data


def _load_script(name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(REPO, "scripts", f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_build_portable_missing_dist_fails(monkeypatch, tmp_path):
    mod = _load_script("build_portable")
    monkeypatch.setattr(mod, "REPO", str(tmp_path), raising=False)
    with pytest.raises(SystemExit) as e:
        mod.build_portable("9.9.9")
    assert e.value.code == 2


def test_write_checksums(monkeypatch, tmp_path):
    mod = _load_script("build_portable")
    monkeypatch.setattr(mod, "REPO", str(tmp_path), raising=False)
    f = tmp_path / "f.bin"
    f.write_bytes(b"data")
    sums = mod.write_checksums("1.0.0", [str(f)])
    body = open(sums).read()
    assert "f.bin" in body and hashlib.sha256(b"data").hexdigest() in body


def test_packaging_lint_passes():
    """The repo's own packaging inputs must pass scripts/lint_packaging.py."""
    mod = _load_script("lint_packaging")
    assert mod.main() == 0
    assert mod.ERRORS == []
