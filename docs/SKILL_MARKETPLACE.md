# Signed Skill Marketplace (Phase 9 moonshot)

Community skills, installed safely: every package is **signed** (Ed25519),
**hash-pinned** (every file), **revocable**, and gated by the existing
sandbox + policy rails. A malicious package is refused at install time —
its code is never executed during install or verify.

## Trust model

| Tier | Meaning | Install | Tool risk | Sandbox |
|---|---|---|---|---|
| `unsigned` | No (valid) signature | **REFUSED** | — | — |
| `self-signed` | Valid sig, unknown key | Explicit confirm | Forced `DESTRUCTIVE` | Level B+ |
| `curator` | Valid sig, key in your curator store | Explicit confirm | Manifest tiers honoured (confirm lists every tool + risk) | Level B+ |
| `verified` | Reserved for JARVIS-project-endorsed keys | — | — | — |

* **Self-signed** = "I trust this author personally." You confirm each
  install; all tools run at the DESTRUCTIVE floor (raise-only rule from
  Task 4.6.3 still applies).
* **Curator** = "a reviewer I trust checked this." Add curator keys with
  `jarvis skill trust add <pubkey>`. The key ceremony (who the curators
  are) is a community decision — the store ships empty.
* **Verified** is reserved for a future project-run key ceremony. Today it
  behaves like `curator`.
* Trust is **re-verified on every load**: the install record
  (`.marketplace.json`) pins every file hash; a modified install
  downgrades to `third_party` automatically.

## Quick start

### Installing a skill

```bash
jarvis skill verify ./cool-skill-1.0.0.jskill   # inspect first
jarvis skill install ./cool-skill-1.0.0.jskill  # prompts: author, key,
                                                # trust, permissions, tools
```

Install refuses when: the signature is bad, any hash mismatches, the key
or package is revoked, sandbox is below Level B, or you don't confirm.
Non-interactive shells always refuse.

### For authors: publishing a skill

```bash
# 1. One-time: generate a signing key (private key -> 0600 file, never shared)
jarvis skill keygen
#    public key:  <64 hex chars>   <- put this in your README / profile
#    key id:      <16 hex chars>

# 2. Build + sign your skill dir (needs SKILL.md + tool.py)
jarvis skill package ./my-skill ~/.jarvis/marketplace/keys/<key-id>.key "Your Name"
#    -> my-skill-1.0.0.jskill

# 3. Share the .jskill file (GitHub release, forum post, ...).
#    Users verify with: jarvis skill verify my-skill-1.0.0.jskill
```

Rules for authors:

* Declare **all** permissions up front in `SKILL.md` — the package
  manifest must match exactly, or installs are refused.
* Keep packages small (< 50 MB total); no symlinks, no absolute paths.
* Bump `version` (X.Y.Z) on every release; never re-sign the same version
  with different content.

### For curators: reviewing a skill

1. `jarvis skill verify package.jskill` — signature, hashes, manifest.
2. Read `SKILL.md` + `tool.py` fully. Checklist:
   - [ ] Permissions declared == permissions used (no `net:*` surprises).
   - [ ] Tool risk tiers are honest (`reversible` really is reversible).
   - [ ] No exfiltration: check every network call and file write.
   - [ ] No obfuscation; no `eval`/`exec` on remote input.
   - [ ] `tool.py` has no import-time side effects.
3. Publish your review; users add your key via
   `jarvis skill trust add <your-pubkey> "Your Name"`.

### Revocation

Curators publish a **signed JSON feed** (`jarvis-revocation-feed/1`):

```json
{
  "format": "jarvis-revocation-feed/1",
  "issued_at": "2026-11-03T20:00:00",
  "revoked_keys": ["<key-id>"],
  "revoked_packages": ["bad-skill@1.0.0"],
  "signature": {"algorithm": "ed25519", "key_id": "...",
                "public_key": "...", "signature": "..."}
}
```

Users apply it offline:

```bash
jarvis skill update-revocations feed.json <curator-pubkey-hex>
```

The local cache (`~/.jarvis/marketplace/revoked.json`) is checked on
every install/verify — no network needed. A tampered feed is ignored
(signature must verify against the curator key you pass).

## Package format (`jarvis-skill-package/1`)

A `.jskill` is a zip (or directory) containing:

* `MANIFEST.json` — `{format, name, version, author, author_key_id,
  min_jarvis, permissions[], files{path: sha256}}`. Strict schema:
  unknown fields are rejected.
* `SIGNATURE.json` — `{algorithm: "ed25519", key_id, public_key,
  signature}` over the canonical (sorted-keys, compact) MANIFEST bytes.
  `key_id` must equal `sha256(public_key)[:16]` and match
  `author_key_id`.
* `SKILL.md`, `tool.py`, … — every file hash-pinned; unpinned extras
  are refused.

## Cryptography notes

* Ed25519 is implemented in pure Python (`marketplace/ed25519.py`,
  stdlib only) and pinned against libsodium-generated vectors in the
  test suite. It is **not constant-time** — sign on a trusted machine.
* For HSM-backed deployments, swap the module for `cryptography`;
  call sites only use `keypair`/`sign`/`verify`/`key_id`.

## Out of scope (moonshot boundaries)

* **Registry server** — there is no hosted marketplace yet; distribution
  is files (releases, forums). The feed *format* is specified so a
  server can adopt it later.
* **Key ceremony** — who the `verified` keys belong to is undecided.
* **Auto-update** — upgrades are manual (`uninstall` + `install`);
  auto-update of third-party code is deliberately not built.
* **Windows signing** — this signs *skills*, not the JARVIS installer
  (that's the OS code-signing cert, Task 8.4).
