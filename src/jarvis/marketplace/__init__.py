"""Signed skill marketplace (Phase 9 moonshot).

Submodules:

* :mod:`jarvis.marketplace.ed25519` — pure-Python Ed25519 (RFC 8032).
* :mod:`jarvis.marketplace.package` — ``.jskill`` format, parse-only.
* :mod:`jarvis.marketplace.signing` — sign/verify + curator trust store.
* :mod:`jarvis.marketplace.revocation` — revocation cache + signed feeds.
* :mod:`jarvis.marketplace.installer` — fail-closed install flow.
"""

from jarvis.marketplace import ed25519, installer, package, revocation, signing

__all__ = ["ed25519", "installer", "package", "revocation", "signing"]
