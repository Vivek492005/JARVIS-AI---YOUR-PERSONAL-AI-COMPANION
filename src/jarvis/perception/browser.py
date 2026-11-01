"""Browser automation (Master Plan Task 5.5).

Playwright behind the :class:`BrowserBackend` protocol, always on a
**dedicated "jarvis" profile** — never the user's main profile/cookies
(the real backend is responsible for launching with that profile; the
fake used in tests just records).

Safety rails (all enforced here, before the policy gate):
- **Scheme blocklist:** ``file://``, ``chrome://``, ``about:``,
  ``data:``, ``javascript:`` are refused outright.
- **Domain denylist** always enforced; optional allowlist mode
  (``browser.allowed_domains`` in settings) restricts to listed domains.
- **Handoff:** login / payment / 2FA pages never get automated —
  ``browser_submit`` on such a page returns the handoff message instead
  of submitting, and ``browser_open`` warns when the URL smells like
  auth/payment.
- ``browser_read`` results are ``carries_external_data`` (untrusted).
- Downloads belong in the scoped workspace (Task 5.6); executable
  file types are refused.

Tools: ``browser_open`` (REVERSIBLE), ``browser_read`` (READ),
``browser_click`` / ``browser_fill`` (REVERSIBLE), ``browser_submit``
(DESTRUCTIVE — sends data outward).
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional
from urllib.parse import urlparse

from jarvis.perception import backends as _backends

logger = logging.getLogger(__name__)

# Schemes that are never opened, no exceptions.
BLOCKED_SCHEMES = frozenset({
    "file", "chrome", "chrome-extension", "about", "data",
    "javascript", "vbscript",
})

# Domains never automated (phishing/malware-adjacent placeholders;
# extend via settings).
DOMAIN_DENYLIST = frozenset({
    "localhost",  # SSRF guard: the agent browser must not probe local services
})

# URL/snapshot hints that a page is auth or payment -> handoff.
AUTH_PAYMENT_HINTS = (
    "login", "log-in", "signin", "sign-in", "password",
    "2fa", "two-factor", "otp", "captcha",
    "payment", "checkout", "pay now", "card number", "billing",
)

HANDOFF_MESSAGE = ("Mujhse nahi hoga, aap kar do — "
                   "yeh login/payment wala page hai.")

# Downloadable-but-dangerous extensions refused outright.
BLOCKED_DOWNLOAD_EXTS = frozenset({
    ".exe", ".msi", ".bat", ".cmd", ".ps1", ".vbs", ".js", ".jar",
    ".scr", ".com", ".pif", ".dll",
})


class BrowserBlocked(Exception):
    """URL/scheme/domain refused by the browser safety rails."""


def _check_url(url: str, allowed_domains: Optional[List[str]] = None) -> str:
    """Validate a URL. Returns the normalized URL or raises BrowserBlocked."""
    url = (url or "").strip()
    if not url:
        raise BrowserBlocked("empty URL")
    # Detect an explicit scheme FIRST (data:, javascript:, ...), before
    # assuming https:// — otherwise "data:text/html" would smuggle through.
    parsed = urlparse(url)
    if not parsed.scheme:
        url = "https://" + url
        parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise BrowserBlocked(f"blocked scheme: {scheme}:")
    host = (parsed.hostname or "").lower()
    if not host:
        raise BrowserBlocked("URL has no host")
    if host in DOMAIN_DENYLIST:
        raise BrowserBlocked(f"denylisted domain: {host}")
    if allowed_domains:
        allowed = {d.lower() for d in allowed_domains}
        if host not in allowed and not any(
                host.endswith("." + d) for d in allowed):
            raise BrowserBlocked(f"domain not in allowlist: {host}")
    return url


def _looks_like_auth_or_payment(url: str, snapshot: str = "") -> bool:
    hay = f"{url} {snapshot}".lower()
    return any(h in hay for h in AUTH_PAYMENT_HINTS)


def check_download_filename(name: str) -> None:
    """Refuse executable downloads."""
    lowered = (name or "").lower()
    for ext in BLOCKED_DOWNLOAD_EXTS:
        if lowered.endswith(ext):
            raise BrowserBlocked(f"executable download refused: {name}")


class BrowserController:
    """DOM automation controller. Backend injected via backends registry."""

    def __init__(self, backend=None,
                 allowed_domains: Optional[List[str]] = None) -> None:
        self._backend = backend
        self._allowed = allowed_domains

    def _be(self):
        return self._backend or _backends.get_backend("browser")

    def _settings_allowlist(self) -> Optional[List[str]]:
        if self._allowed is not None:
            return self._allowed
        try:
            from jarvis.core.config import get_settings
            domains = getattr(get_settings().browser, "allowed_domains", None)
            return list(domains) if domains else None
        except Exception:
            return None

    def open(self, url: str) -> str:
        url = _check_url(url, self._settings_allowlist())
        out = self._be().open(url)
        if _looks_like_auth_or_payment(url):
            out += (" NOTE: this looks like a login/payment page — "
                    "automation will hand off for sensitive steps.")
        return out

    def read(self) -> str:
        """Accessibility snapshot (untrusted external data)."""
        return self._be().snapshot()

    def click(self, ref: str) -> str:
        return self._be().click(ref)

    def fill(self, ref: str, value: str) -> str:
        return self._be().fill(ref, value)

    def submit(self, ref: Optional[str] = None) -> str:
        """Submit a form. Refuses on auth/payment pages (handoff)."""
        url = ""
        snapshot = ""
        try:
            url = self._be().current_url or ""
        except Exception:
            pass
        try:
            snapshot = self._be().snapshot() or ""
        except Exception:
            pass
        if _looks_like_auth_or_payment(url, snapshot):
            return HANDOFF_MESSAGE
        return self._be().submit(ref)

    @property
    def current_url(self) -> str:
        try:
            return self._be().current_url or ""
        except Exception:
            return ""
