"""Tests for the pure-Python Ed25519 module.

Regression vectors were generated with libsodium (via pynacl) and pinned
here; the implementation agreed with libsodium on pubkey derivation and
deterministic signatures across 8 random seeds plus these fixed vectors.
"""

import pytest

from jarvis.marketplace.ed25519 import key_id, keypair, sign, verify

# seed -> (public_key, {message_name: (message, signature)})
VECTORS = [
    (
        "0102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f20",
        "79b5562e8fe654f94078b112e8a98ba7901f853ae695bed7e0e3910bad049664",
        {
            "empty": (
                b"",
                "d9452bd4cc80bcecf4a18895094646e91a5a9bbf1b2707e05396b2cf67c9c2b7"
                "d9b847a0d562425ccbb71038c7649fdcbfd76ee0e8247c8ec9326999b6256a0b",
            ),
            "hello": (
                b"hello marketplace",
                "786d604ce416adbd54bbfb30a361dfbdb09bf76f2f0ad09ef7d41712963b61d2"
                "481bb27c493eabc5fc9006c2c0fc6b9309f3f3bfd84d772be0ff3c85eabc2108",
            ),
        },
    ),
    (
        "ffeeddccbbaa99887766554433221100ffeeddccbbaa99887766554433221100",
        "2e4e83fdb2d88f88c5f03e663c39ea3f9c7536312b62a2b09a95712dccf11a40",
        {
            "empty": (
                b"",
                "84e4fed906a342aab415a2abc72b9ce9703f616fe850dc3a1ffb1f4873760f25"
                "bd73bd6881bc495a1a87bf801c044f5516f2380cca43808a9913969552912a00",
            ),
            "hello": (
                b"hello marketplace",
                "48933195bccf3668bfa9ed0afc55fb3b002208186be083f890f34f3e96a1414e"
                "2da96b01cb1fb445fd0c8312811b6ea49ab9d467c20f750891e3b0974f42190e",
            ),
        },
    ),
]


@pytest.mark.parametrize("seed_hex,pub_hex,sigs", VECTORS)
def test_keypair_derives_pinned_pubkey(seed_hex, pub_hex, sigs):
    seed = bytes.fromhex(seed_hex)
    _, pub = keypair(seed)
    assert pub.hex() == pub_hex


@pytest.mark.parametrize("seed_hex,pub_hex,sigs", VECTORS)
def test_sign_matches_pinned_signature(seed_hex, pub_hex, sigs):
    seed = bytes.fromhex(seed_hex)
    for _name, (msg, sig_hex) in sigs.items():
        assert sign(seed, msg).hex() == sig_hex


@pytest.mark.parametrize("seed_hex,pub_hex,sigs", VECTORS)
def test_verify_accepts_pinned(seed_hex, pub_hex, sigs):
    pub = bytes.fromhex(pub_hex)
    for _name, (msg, sig_hex) in sigs.items():
        assert verify(pub, msg, bytes.fromhex(sig_hex))


@pytest.mark.parametrize("seed_hex,pub_hex,sigs", VECTORS)
def test_verify_rejects_tampered_message(seed_hex, pub_hex, sigs):
    pub = bytes.fromhex(pub_hex)
    for _name, (msg, sig_hex) in sigs.items():
        assert not verify(pub, msg + b"!", bytes.fromhex(sig_hex))


@pytest.mark.parametrize("seed_hex,pub_hex,sigs", VECTORS)
def test_verify_rejects_tampered_signature(seed_hex, pub_hex, sigs):
    pub = bytes.fromhex(pub_hex)
    for _name, (msg, sig_hex) in sigs.items():
        bad = bytearray(bytes.fromhex(sig_hex))
        bad[63] ^= 1
        assert not verify(pub, msg, bytes(bad))


def test_verify_rejects_wrong_key():
    pub0 = bytes.fromhex(VECTORS[0][1])
    sig1 = bytes.fromhex(VECTORS[1][2]["hello"][1])
    assert not verify(pub0, b"hello marketplace", sig1)


def test_verify_rejects_garbage_lengths():
    pub = bytes.fromhex(VECTORS[0][1])
    assert not verify(pub, b"m", b"\x00" * 64)
    assert not verify(pub, b"m", b"\x00" * 63)
    assert not verify(b"\x00" * 31, b"m", b"\x00" * 64)


def test_sign_is_deterministic():
    seed, _ = keypair()
    assert sign(seed, b"abc") == sign(seed, b"abc")


def test_keypair_random_and_sized():
    seed, pub = keypair()
    assert len(seed) == 32 and len(pub) == 32
    seed2, pub2 = keypair()
    assert seed != seed2 and pub != pub2


def test_keypair_rejects_bad_seed():
    with pytest.raises(ValueError):
        keypair(b"short")


def test_key_id_format_and_stability():
    _, pub = keypair()
    kid = key_id(pub)
    assert len(kid) == 16 and all(c in "0123456789abcdef" for c in kid)
    assert key_id(pub) == kid
    _, pub2 = keypair()
    assert key_id(pub2) != kid
