"""Pure-Python Ed25519 (RFC 8032) — zero third-party dependencies.

Adapted from the public-domain reference implementation by Daniel J.
Bernstein, Niels Duif, Tanja Lange, Peter Schwabe and Bo-Yin Yang
("High-speed high-security signatures"). Correctness is pinned by the
RFC 8032 section 7.1 test vectors in the test suite.

Only what the skill marketplace needs is exposed: :func:`keypair`,
:func:`sign`, :func:`verify` and :func:`key_id`.

Security notes (read before using outside the marketplace):
* This is NOT constant-time. ``sign`` handles secret scalars, so run it
  on a trusted machine; verification (the hot path) touches no secrets.
* For HSM-backed or high-assurance deployments, swap this module for
  ``cryptography`` — the call sites only depend on the four functions
  above, all of which have identical signatures there.
"""

from __future__ import annotations

import hashlib
import os

__all__ = ["keypair", "sign", "verify", "key_id"]

_b = 256
_q = (1 << 255) - 19
_l = (1 << 252) + 27742317777372353535851937790883648493


def _H(m: bytes) -> bytes:
    return hashlib.sha512(m).digest()


def _inv(x: int) -> int:
    return pow(x, _q - 2, _q)


_d = (-121665 * _inv(121666)) % _q
_I = pow(2, (_q - 1) // 4, _q)


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * _inv(_d * y * y + 1)
    x = pow(xx, (_q + 3) // 8, _q)
    if (x * x - xx) % _q != 0:
        x = (x * _I) % _q
    if x % 2 != 0:
        x = _q - x
    return x


_By = (4 * _inv(5)) % _q
_Bx = _xrecover(_By)
_B = [_Bx % _q, _By % _q]


def _edwards(P: list, Q: list) -> list:
    # Addition law for the twisted Edwards curve -x^2 + y^2 = 1 + d*x^2*y^2
    # (note the + sign in y3 — the a=+1 variant uses a minus there).
    x1, y1 = P
    x2, y2 = Q
    x3 = (x1 * y2 + x2 * y1) * _inv(1 + _d * x1 * x2 * y1 * y2)
    y3 = (y1 * y2 + x1 * x2) * _inv(1 - _d * x1 * x2 * y1 * y2)
    return [x3 % _q, y3 % _q]


def _scalarmult(P: list, e: int) -> list:
    if e == 0:
        return [0, 1]
    Q = _scalarmult(P, e // 2)
    Q = _edwards(Q, Q)
    if e & 1:
        Q = _edwards(Q, P)
    return Q


def _encodeint(y: int) -> bytes:
    bits = [(y >> i) & 1 for i in range(_b)]
    return b"".join(
        bytes([sum(bits[i * 8 + j] << j for j in range(8))])
        for i in range(_b // 8)
    )


def _encodepoint(P: list) -> bytes:
    x, y = P
    bits = [(y >> i) & 1 for i in range(_b - 1)] + [x & 1]
    return b"".join(
        bytes([sum(bits[i * 8 + j] << j for j in range(8))])
        for i in range(_b // 8)
    )


def _bit(h: bytes, i: int) -> int:
    return (h[i // 8] >> (i % 8)) & 1


def _publickey(sk: bytes) -> bytes:
    h = _H(sk)
    a = 2 ** (_b - 2) + sum(2 ** i * _bit(h, i) for i in range(3, _b - 2))
    return _encodepoint(_scalarmult(_B, a))


def _Hint(m: bytes) -> int:
    h = _H(m)
    return sum(2 ** i * _bit(h, i) for i in range(2 * _b))


def _signature(m: bytes, sk: bytes, pk: bytes) -> bytes:
    h = _H(sk)
    a = 2 ** (_b - 2) + sum(2 ** i * _bit(h, i) for i in range(3, _b - 2))
    r = _Hint(h[_b // 8:_b // 4] + m)
    R = _scalarmult(_B, r)
    S = (r + _Hint(_encodepoint(R) + pk + m) * a) % _l
    return _encodepoint(R) + _encodeint(S)


def _isoncurve(P: list) -> bool:
    x, y = P
    return (-x * x + y * y - 1 - _d * x * x * y * y) % _q == 0


def _decodeint(s: bytes) -> int:
    return sum(2 ** i * _bit(s, i) for i in range(_b))


def _decodepoint(s: bytes) -> list:
    y = sum(2 ** i * _bit(s, i) for i in range(_b - 1))
    x = _xrecover(y)
    if x & 1 != _bit(s, _b - 1):
        x = _q - x
    P = [x, y]
    if not _isoncurve(P):
        raise ValueError("point is not on the curve")
    return P


def _checkvalid(s: bytes, m: bytes, pk: bytes) -> None:
    if len(s) != _b // 4:
        raise ValueError("bad signature length")
    if len(pk) != _b // 8:
        raise ValueError("bad public-key length")
    R = _decodepoint(s[:_b // 8])
    A = _decodepoint(pk)
    S = _decodeint(s[_b // 8:_b // 4])
    h = _Hint(_encodepoint(R) + pk + m)
    v1 = _scalarmult(_B, S)
    v2 = _edwards(R, _scalarmult(A, h))
    if v1 != v2:
        raise ValueError("signature verification failed")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def keypair(seed: bytes | None = None) -> tuple[bytes, bytes]:
    """Generate an Ed25519 keypair. Returns (secret_seed, public_key).

    ``secret_seed`` is 32 random bytes; the public key is 32 bytes.
    """
    if seed is None:
        seed = os.urandom(32)
    if len(seed) != 32:
        raise ValueError("seed must be 32 bytes")
    return bytes(seed), _publickey(bytes(seed))


def sign(secret_seed: bytes, message: bytes) -> bytes:
    """Sign ``message``; returns the 64-byte signature."""
    if len(secret_seed) != 32:
        raise ValueError("secret seed must be 32 bytes")
    pk = _publickey(bytes(secret_seed))
    return _signature(bytes(message), bytes(secret_seed), pk)


def verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    """Fail-closed verification: True iff the signature is valid."""
    try:
        _checkvalid(bytes(signature), bytes(message), bytes(public_key))
        return True
    except Exception:
        return False


def key_id(public_key: bytes) -> str:
    """Short identifier for a key: first 16 hex chars of sha256(pubkey)."""
    return hashlib.sha256(bytes(public_key)).hexdigest()[:16]
