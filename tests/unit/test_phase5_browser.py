"""Tests for Phase 5.5 browser automation safety rails."""

import sys

import pytest

sys.path.insert(0, "src")
sys.path.insert(0, "tests")

from jarvis.perception.browser import (  # noqa: E402
    BrowserBlocked,
    BrowserController,
    _check_url,
    _looks_like_auth_or_payment,
    check_download_filename,
)
from jarvis.tools.registry import REGISTRY, Risk  # noqa: E402
from fakes.fake_desktop import (  # noqa: E402
    FakePage,
    install_fake_desktop,
    uninstall_fake_desktop,
)


@pytest.fixture()
def desktop():
    made = install_fake_desktop()
    made["browser"].add_page(
        FakePage(
            url="https://example.com/form",
            title="Form",
            ax_tree="form [ref=f1]\n  textbox 'Name' [ref=t1]\n  button 'Submit' [ref=b1]",
            refs={"f1": "form", "t1": "name field", "b1": "submit"},
        )
    )
    made["browser"].add_page(
        FakePage(
            url="https://bank.example.com/login",
            title="Login",
            ax_tree="textbox 'Password' [ref=p1]",
            refs={"p1": "password"},
        )
    )
    yield made
    uninstall_fake_desktop()


def test_scheme_blocklist():
    for bad in (
        "file:///etc/passwd",
        "chrome://settings",
        "about:blank",
        "data:text/html,hi",
        "javascript:alert(1)",
    ):
        with pytest.raises(BrowserBlocked):
            _check_url(bad)


def test_plain_host_gets_https():
    assert _check_url("example.com") == "https://example.com"


def test_localhost_denied():
    with pytest.raises(BrowserBlocked):
        _check_url("http://localhost:8080/admin")


def test_allowlist_mode():
    with pytest.raises(BrowserBlocked):
        _check_url("https://evil.com", allowed_domains=["example.com"])
    assert (
        _check_url("https://example.com/x", allowed_domains=["example.com"])
        == "https://example.com/x"
    )
    assert _check_url("https://sub.example.com", allowed_domains=["example.com"]).endswith(
        "sub.example.com"
    )


def test_auth_payment_hints():
    assert _looks_like_auth_or_payment("https://x.com/login")
    assert _looks_like_auth_or_payment("https://x.com/", "Enter card number")
    assert not _looks_like_auth_or_payment("https://example.com/form", "Name")


def test_download_exe_refused():
    with pytest.raises(BrowserBlocked):
        check_download_filename("setup.exe")
    check_download_filename("notes.pdf")  # fine


def test_open_read_click_fill(desktop):
    ctl = BrowserController()
    out = ctl.open("https://example.com/form")
    assert "opened" in out
    snap = ctl.read()
    assert "textbox 'Name'" in snap
    assert "clicked" in ctl.click("b1")
    assert "filled" in ctl.fill("t1", "Vivek")


def test_open_login_page_warns(desktop):
    ctl = BrowserController()
    out = ctl.open("https://bank.example.com/login")
    assert "hand off" in out


def test_submit_hands_off_on_login(desktop):
    ctl = BrowserController()
    ctl.open("https://bank.example.com/login")
    out = ctl.submit()
    assert "Mujhse nahi hoga" in out
    # never reached the backend
    assert ("submit", (None,)) not in ctl._be().actions


def test_submit_ok_on_plain_form(desktop):
    ctl = BrowserController()
    ctl.open("https://example.com/form")
    assert ctl.submit() == "submitted"


def test_tools_registered():
    assert REGISTRY["browser_open"].risk == Risk.REVERSIBLE
    assert REGISTRY["browser_read"].risk == Risk.READ
    assert REGISTRY["browser_read"].carries_external_data is True
    assert REGISTRY["browser_click"].risk == Risk.REVERSIBLE
    assert REGISTRY["browser_fill"].risk == Risk.REVERSIBLE
    assert REGISTRY["browser_submit"].risk == Risk.DESTRUCTIVE


def test_run_action_browser_blocked_scheme(desktop):
    from jarvis.tools.actions import execute_tool_raw, run_action

    verdict, result = run_action("browser_open", {"url": "file:///etc/passwd"})
    # Gate asks for confirmation (REVERSIBLE at L1)...
    assert verdict == "confirm", (verdict, result)
    # ...but even a CONFIRMED call is refused by the handler rails.
    out = execute_tool_raw("browser_open", {"url": "file:///etc/passwd"})
    assert "Blocked" in out and "file" in out
