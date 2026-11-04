"""`jarvis` command-line interface (Master Plan Task 2.4).

Commands:
  jarvis serve [--http] [--port PORT]   run jarvisd (headless service)
  jarvis ui                             tkinter GUI as a service client
  jarvis send "text" [--url URL]        send one command (needs serve --http)
  jarvis doctor                         diagnostics (Task 2.7)
  jarvis reflex stats                   reflex-layer coverage (Task 2.6)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

logger = logging.getLogger("jarvis.cli")


def _start_summon_ui(port: int, token: str) -> None:
    """Best-effort tray icon + global hotkey that open the buddy.

    The buddy (buddy.html) is the default summon surface: a small floating
    companion; clicking it expands the compact chat card. Ctrl+Alt+J (or the
    tray "Open chat" item) opens ``/hud/buddy.html?token=...`` in the default
    browser. Everything is availability-guarded; any failure only logs a
    warning and never breaks ``serve``. Windows-only in practice
    (pystray/keyboard).
    """
    try:
        import webbrowser
        from jarvis.hud.tray import TrayController, HotkeySummon

        url = f"http://127.0.0.1:{port}/hud/buddy.html?token={token}"

        def _open_chat() -> None:
            try:
                webbrowser.open(url)
            except Exception:
                logger.warning("summon: could not open browser", exc_info=True)

        tray = TrayController(on_show=_open_chat, on_summon=_open_chat)
        if tray.available:
            import threading
            threading.Thread(target=tray.run, daemon=True,
                             name="jarvis-tray").start()
            logger.info("tray icon running (Open chat / Summon / Quit)")
        else:
            logger.info("tray unavailable (pystray/Pillow not installed)")

        hotkey = HotkeySummon(on_summon=_open_chat)
        if hotkey.available:
            hotkey.start()
            logger.info("summon hotkey registered: %s", hotkey.hotkey)
        else:
            logger.info("hotkey unavailable ('keyboard' package not installed)")
    except Exception:
        logger.warning("summon UI failed to start", exc_info=True)


def _cmd_serve(args) -> int:
    from jarvis.server.service import JarvisService
    from jarvis.server.token import get_or_create_token

    service = JarvisService()
    service.start()
    try:
        if args.http:
            try:
                import uvicorn  # noqa: F401
            except ImportError:
                print("jarvis serve --http needs the 'server' extra:\n"
                      "  pip install jarvis-assistant[server]", file=sys.stderr)
                return 2
            from jarvis.server.api import create_app
            token = get_or_create_token()
            app = create_app(service, token)
            print(f"jarvisd HTTP on http://127.0.0.1:{args.port} "
                  f"(token stored per-install; see server.token)")
            _start_summon_ui(args.port, token)
            uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info")
        else:
            print("jarvisd running (in-process, no HTTP). "
                  "Use --http to expose the API. Ctrl+C to stop.")
            import threading
            threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        service.stop()
    return 0


def _cmd_ui(args) -> int:
    """Tkinter GUI as a client of the in-process service (Task 2.4)."""
    from jarvis.server.service import JarvisService
    from jarvis.server.client import JarvisClient

    service = JarvisService()
    service.start()
    client = JarvisClient(service)

    # The GUI talks to an "assistant" object; adapt the client to it.
    class _ClientAssistant:
        def __init__(self, client, service):
            self._client = client
            self._service = service
            self.voice = None  # wired below on Windows

        def send_text_command(self, text):
            self._client.send_text_command(text)

        def on_voice_command(self, cmd):
            pass

        def stop(self):
            self._service.stop()

    try:
        from gui import JARVISGUI
    except ImportError as e:
        print(f"GUI unavailable: {e}", file=sys.stderr)
        return 2

    assistant = _ClientAssistant(client, service)
    # Voice control for mic buttons (Windows only; best-effort).
    try:
        from jarvis.voice.interface import VoiceInterface
        assistant.voice = VoiceInterface(status_callback=lambda s: None)
    except Exception as e:
        logger.warning("voice unavailable: %s", e)

    gui = JARVISGUI(assistant)
    try:
        gui.show()
    finally:
        service.stop()
    return 0


def _cmd_send(args) -> int:
    from jarvis.server.client import HttpJarvisClient
    from jarvis.server.token import get_or_create_token
    token = args.token or get_or_create_token()
    client = HttpJarvisClient(args.url, token)
    try:
        print(client.send_command(args.text))
    finally:
        client.close()
    return 0


def _cmd_onboard(args) -> int:
    """Task 7.6: interactive first-run wizard."""
    from pathlib import Path
    from jarvis.core import config as config_mod
    from jarvis.core import secrets as secrets_mod
    from jarvis.onboarding.wizard import OnboardingWizard, StepContext

    cfg = config_mod.get_settings()
    workspace = Path(cfg.memory_workspace or (Path.home() / ".jarvis" / "workspace"))

    def _mic_test():
        try:
            from jarvis.voice.audio import record_sample_rms  # type: ignore
            return record_sample_rms(seconds=2.0)
        except Exception as e:
            return {"skipped": True, "reason": str(e)}

    def _wakeword_test():
        # Real calibration needs the mic loop; the wizard records intent and
        # the threshold stays default until docs/WAKEWORD_TEST.md is followed.
        return {"skipped": True, "reason": "follow docs/WAKEWORD_TEST.md"}

    def _run_doctor():
        from jarvis.core.doctor import run_doctor
        rc = run_doctor()
        return {"ok": rc == 0, "summary": f"exit={rc}"}

    ctx = StepContext(
        config=cfg,
        workspace=workspace,
        store_secret=secrets_mod.store_secret,
        mic_test=_mic_test,
        wakeword_test=_wakeword_test,
        run_command=lambda c: f"(demo skipped — run 'jarvis send {c!r}' with jarvisd up)",
        run_doctor=_run_doctor,
    )
    wiz = OnboardingWizard(ctx)
    wiz.run()
    try:
        config_mod._write_settings_toml(cfg)
    except Exception as e:
        print(f"warning: config not saved: {e}")
    return 0 if wiz.complete else 1


def _cmd_doctor(args) -> int:
    from jarvis.core.doctor import run_doctor
    if getattr(args, "latency", False):
        from jarvis.voice.latency import latency_summary, format_latency_report
        from jarvis.core.metrics import _metrics_dir
        print(format_latency_report(latency_summary(_metrics_dir())))
        return 0
    return run_doctor()


def _cmd_reflex(args) -> int:
    if args.reflex_cmd == "stats":
        from jarvis.brain.reflex import print_stats
        print_stats()
        return 0
    print("usage: jarvis reflex stats", file=sys.stderr)
    return 2


def _skills_dir():
    from pathlib import Path
    from jarvis.core.config import get_settings
    try:
        d = Path(get_settings().brain.skills_dir)
    except Exception:
        d = Path("skills")
    if not d.is_absolute():
        d = Path.cwd() / d
    return d


def _cmd_skill_marketplace(cmd, arg, extra, skills_dir):
    """Marketplace subcommands (Phase 9 moonshot). Returns int or None."""
    from pathlib import Path
    from jarvis.marketplace import ed25519
    from jarvis.marketplace.installer import install_package
    from jarvis.marketplace.installer import _jarvis_version
    from jarvis.marketplace.package import PackageError, build_package, pack_zip
    from jarvis.marketplace.revocation import update_from_feed
    from jarvis.marketplace.signing import (
        CuratorStore, marketplace_dir, sign_package, verify_package,
    )
    from jarvis.marketplace.revocation import check_revoked
    from jarvis.policy.audit import AuditLogger

    def audit(tool, args, decision, reason=""):
        try:
            AuditLogger().log(tool, args, decision, reason)
        except Exception:
            logger = logging.getLogger(__name__)
            logger.exception("marketplace CLI audit write failed")

    if cmd == "install":
        if not arg:
            print("usage: jarvis skill install <package.jskill|dir>",
                  file=sys.stderr)
            return 2
        res = install_package(arg, skills_dir)
        if res.ok:
            print(f"installed {res.name} v{res.version} "
                  f"(trust={res.trust}) -> {res.dest}")
            print("Restart jarvisd to load it.")
            return 0
        print("INSTALL REFUSED:", file=sys.stderr)
        for e in res.errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    if cmd == "verify":
        if not arg:
            print("usage: jarvis skill verify <package.jskill|dir>",
                  file=sys.stderr)
            return 2
        result = verify_package(arg, check_revocation=check_revoked)
        audit("skill.verify",
              {"package": arg, "name": result.name,
               "version": result.version, "key_id": result.key_id,
               "trust": result.trust},
              "allow" if result.ok else "deny",
              "; ".join(result.errors)[:300])
        if result.ok:
            print(f"OK: {result.name} v{result.version} by {result.author}")
            print(f"  trust={result.trust} key={result.key_id}")
            return 0
        print("VERIFY FAILED:", file=sys.stderr)
        for e in result.errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    if cmd == "package":
        # jarvis skill package <skill-dir> <private-key-file> [author-name]
        import shutil
        if not arg or not extra:
            print("usage: jarvis skill package <skill-dir> <private-key-file> "
                  "[author-name]", file=sys.stderr)
            return 2
        key_path = Path(extra[0])
        try:
            seed = bytes.fromhex(key_path.read_text(
                encoding="utf-8").strip().split()[0])
        except (OSError, ValueError) as e:
            print(f"cannot read private key: {e}", file=sys.stderr)
            return 1
        if len(seed) != 32:
            print("private key must be 32 bytes (64 hex chars)",
                  file=sys.stderr)
            return 1
        pub = ed25519.keypair(seed)[1]
        key_id = ed25519.key_id(pub)
        staging = None
        try:
            staging = build_package(
                arg, author=extra[1] if len(extra) > 1 else "anonymous",
                author_key_id=key_id, min_jarvis=_jarvis_version())
            sign_package(staging, seed)
            man = json.loads((staging / "MANIFEST.json").read_text(
                encoding="utf-8"))
            out = pack_zip(staging, Path.cwd() /
                           f"{man['name']}-{man['version']}.jskill")
        except PackageError as e:
            print(f"packaging failed: {e}", file=sys.stderr)
            return 1
        finally:
            if staging is not None:
                shutil.rmtree(staging, ignore_errors=True)
        print(f"signed package: {out} (key {key_id})")
        audit("skill.package", {"skill_dir": arg, "out": str(out),
                                "key_id": key_id}, "allow")
        return 0

    if cmd == "keygen":
        import os as _os
        out = Path(arg) if arg else None
        seed, pub = ed25519.keypair()
        key_id = ed25519.key_id(pub)
        if out is None:
            out = marketplace_dir() / "keys" / f"{key_id}.key"
        out.parent.mkdir(parents=True, exist_ok=True)
        fd = _os.open(out, _os.O_WRONLY | _os.O_CREAT | _os.O_TRUNC, 0o600)
        with _os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(seed.hex() + "\n")
        print(f"private key: {out} (mode 0600 — never share it)")
        print(f"public key:  {pub.hex()}")
        print(f"key id:      {key_id}")
        audit("skill.keygen", {"key_id": key_id,
                               "out": str(out)}, "allow")
        return 0

    if cmd == "trust":
        # jarvis skill trust <add|list|remove> [pubkey-hex|key-id] [name]
        store = CuratorStore()
        sub = arg
        if sub == "list" or sub is None:
            keys = store.list()
            if not keys:
                print("(no curator keys trusted)")
                return 0
            for k in keys:
                print(f"{k.key_id}  {k.name or '(unnamed)'}")
                print(f"    {k.public_key}")
            return 0
        if sub == "add":
            if not extra:
                print("usage: jarvis skill trust add <public-key-hex> [name]",
                      file=sys.stderr)
                return 2
            try:
                key = store.add(extra[0], extra[1] if len(extra) > 1 else "")
            except PackageError as e:
                print(f"bad key: {e}", file=sys.stderr)
                return 1
            print(f"trusted curator key: {key.key_id} ({key.name or 'unnamed'})")
            audit("skill.trust.add", {"key_id": key.key_id,
                                      "name": key.name}, "allow")
            return 0
        if sub == "remove":
            if not extra:
                print("usage: jarvis skill trust remove <key-id>",
                      file=sys.stderr)
                return 2
            if store.remove(extra[0]):
                print(f"removed curator key {extra[0]}")
                audit("skill.trust.remove", {"key_id": extra[0]}, "allow")
                return 0
            print(f"unknown key id: {extra[0]}", file=sys.stderr)
            return 1
        print("usage: jarvis skill trust [add|list|remove]",
              file=sys.stderr)
        return 2

    if cmd == "update-revocations":
        # jarvis skill update-revocations <feed.json> <curator-pubkey-hex>
        if not arg or not extra:
            print("usage: jarvis skill update-revocations <feed.json> "
                  "<curator-public-key-hex>", file=sys.stderr)
            return 2
        try:
            merged = update_from_feed(arg, extra[0])
        except PackageError as e:
            print(f"feed rejected: {e}", file=sys.stderr)
            audit("skill.revocations.update", {"feed": arg}, "deny", str(e))
            return 1
        print(f"revocation cache updated: {len(merged.revoked_keys)} keys, "
              f"{len(merged.revoked_packages)} packages")
        audit("skill.revocations.update", {"feed": arg}, "allow")
        return 0

    return None


def _cmd_skill(args) -> int:
    from jarvis.brain.skills import load_manifest
    from jarvis.brain.skills.scaffold import new_skill

    skills_dir = _skills_dir()
    cmd, arg = args.skill_cmd, args.skill_arg
    extra = getattr(args, "skill_extra", []) or []
    mp = _cmd_skill_marketplace(cmd, arg, extra, skills_dir)
    if mp is not None:
        return mp
    if cmd == "list":
        if not skills_dir.exists():
            print("(no skills dir)")
            return 0
        for child in sorted(skills_dir.iterdir()):
            if not (child / "SKILL.md").exists():
                continue
            try:
                m = load_manifest(child)
                tools = ", ".join(f"{t.name}[{t.risk}]" for t in m.tools)
                print(f"{m.name} v{m.version} [{m.trust.value if hasattr(m, 'trust') else '?'}] - {tools}")
                print(f"    {m.description}")
                if m.permissions:
                    print(f"    permissions: {', '.join(m.permissions)}")
            except Exception as e:
                print(f"{child.name}: ERROR {e}")
        return 0
    if cmd == "new":
        if not arg:
            print("usage: jarvis skill new <name>", file=sys.stderr)
            return 2
        d = new_skill(skills_dir, arg)
        print(f"skill scaffold created: {d}")
        print("Edit SKILL.md, then implement tool.py and restart jarvisd.")
        return 0
    if cmd in ("enable", "disable"):
        # Enable/disable is tracked via a disabled file; the loader skips it.
        if not arg:
            print(f"usage: jarvis skill {cmd} <name>", file=sys.stderr)
            return 2
        flag = skills_dir / arg / ".disabled"
        if cmd == "disable":
            flag.write_text("disabled", encoding="utf-8")
            print(f"skill '{arg}' disabled (restart to apply)")
        else:
            if flag.exists():
                flag.unlink()
            print(f"skill '{arg}' enabled (restart to apply)")
        return 0
    print("usage: jarvis skill [list|new|enable|disable|install|verify|"
          "package|keygen|trust|update-revocations]", file=sys.stderr)
    return 2


def _cmd_learn(args) -> int:
    """Self-improving skills loop (Phase 9 moonshot). Never auto-applies:
    approve/reject/revert are explicit human decisions, audit-logged."""
    from jarvis.learning.service import LearningService
    svc = LearningService.default()
    cmd, arg = args.learn_cmd, args.learn_arg
    extra = getattr(args, "learn_extra", []) or []

    if cmd == "status":
        s = svc.status()
        print(f"learning loop: {'ENABLED' if s['enabled'] else 'DISABLED'}")
        print(f"  runs: {s['total_runs']} ({s['learnable_runs']} learnable)")
        print(f"  corrections: {s['total_corrections']}")
        print(f"  pending proposals: {s['pending_proposals']}")
        return 0
    if cmd in ("enable", "disable"):
        s = svc.set_enabled(cmd == "enable")
        print("learning loop", "ENABLED" if s["enabled"] else "DISABLED")
        return 0
    if cmd == "analyze":
        out = svc.analyze()
        total = sum(len(v) for v in out.values())
        print(f"{total} new proposal(s):")
        for t, ids in out.items():
            for pid in ids:
                print(f"  [{t}] {pid}")
        return 0
    if cmd == "ingest-audit":
        out = svc.ingest_audit()
        print(f"ingested {out['ingested']} audit entr(y/ies)")
        return 0
    if cmd == "proposals":
        for p in svc.reviewer.list(status=arg or ""):
            print(f"{p['id']} [{p['type']}] ({p['status']}) "
                  f"conf={p['confidence']}: {p['title']}")
        return 0
    if cmd == "approve":
        if not arg:
            print("usage: jarvis learn approve <proposal-id>", file=sys.stderr)
            return 2
        print(f"approving {arg} — eval gate running (may take minutes)…")
        out = svc.approve(arg, reviewer="cli")
        print(out.message)
        return 0 if out.ok else 1
    if cmd == "reject":
        if not arg:
            print("usage: jarvis learn reject <proposal-id> [reason]",
                  file=sys.stderr)
            return 2
        out = svc.reviewer.reject(arg, reason=" ".join(extra),
                                  reviewer="cli")
        print(out.message)
        return 0 if out.ok else 1
    if cmd == "revert":
        if not arg:
            print("usage: jarvis learn revert <applied-id>", file=sys.stderr)
            return 2
        try:
            aid = int(arg)
        except ValueError:
            print("applied-id must be a number", file=sys.stderr)
            return 2
        out = svc.reviewer.revert(aid, reviewer="cli")
        print(out.message)
        return 0 if out.ok else 1
    print(f"unknown learn command: {cmd}", file=sys.stderr)
    return 2


def _cmd_memory(args) -> int:
    from jarvis.brain.memory.commands import MemoryCommands, parse
    from jarvis.brain.memory.store import MemoryStore
    store = MemoryStore()
    mc = MemoryCommands(store)
    cmd, arg = args.memory_cmd, args.memory_arg or ""
    if cmd == "list":
        print(mc.handle(parse("tumhe kya yaad hai?")))
    elif cmd == "forget":
        print(mc.handle(parse(f"bhool ja {arg}")))
    elif cmd == "remember":
        print(mc.handle(parse(f"yaad rakhna {arg}")))
    elif cmd == "export":
        print(mc.handle(parse("memory export")))
    elif cmd == "wipe":
        out = mc.handle(parse("memory delete all"))
        if out.startswith("CONFIRM_WIPE:"):
            print(out)
            answer = input("Confirm wipe? (haan/nahi): ").strip().lower()
            if answer in ("haan", "yes", "y"):
                print(mc.confirm_wipe())
            else:
                print("Cancelled.")
        else:
            print(out)
    else:
        print("usage: jarvis memory [list|forget|export|wipe|remember]",
              file=sys.stderr)
        return 2
    store.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="jarvis", description="JARVIS AI companion")
    # Task 8.3: global safe mode — only reflex + READ tools run.
    p.add_argument("--safe", action="store_true",
                   help="safe mode: only reflex + READ tools (fail-closed)")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("serve", help="run jarvisd (headless service)")
    s.add_argument("--http", action="store_true", help="expose the HTTP/WS API")
    s.add_argument("--port", type=int, default=8765)
    s.set_defaults(func=_cmd_serve)

    u = sub.add_parser("ui", help="tkinter GUI as a service client")
    u.set_defaults(func=_cmd_ui)

    snd = sub.add_parser("send", help="send one command to a running jarvisd")
    snd.add_argument("text")
    snd.add_argument("--url", default="http://127.0.0.1:8765")
    snd.add_argument("--token", default=None)
    snd.set_defaults(func=_cmd_send)

    d = sub.add_parser("doctor", help="run diagnostics (Task 2.7)")
    d.add_argument("--latency", action="store_true",
                   help="latency budget report (Task 3.10)")
    d.set_defaults(func=_cmd_doctor)

    o = sub.add_parser("onboard", help="first-run setup wizard (Task 7.6)")
    o.set_defaults(func=_cmd_onboard)

    r = sub.add_parser("reflex", help="reflex layer utilities (Task 2.6)")
    r.add_argument("reflex_cmd", nargs="?", default="stats")
    r.set_defaults(func=_cmd_reflex)

    sk = sub.add_parser("skill", help="skill management (Task 4.6)")
    sk.add_argument("skill_cmd", nargs="?", default="list",
                    help="list | new <name> | enable <name> | disable <name> | "
                         "install <pkg> | verify <pkg> | package <dir> <key> | "
                         "keygen | trust [add|list|remove] | update-revocations")
    sk.add_argument("skill_arg", nargs="?", default=None)
    sk.add_argument("skill_extra", nargs="*", default=[])
    sk.set_defaults(func=_cmd_skill)

    mem = sub.add_parser("memory", help="memory controls (Task 4.4)")
    mem.add_argument("memory_cmd", nargs="?", default="list",
                     help="list | forget <text> | export | wipe | remember <text>")
    mem.add_argument("memory_arg", nargs="?", default=None)
    mem.set_defaults(func=_cmd_memory)

    ln = sub.add_parser("learn", help="self-improving skills loop (Phase 9)")
    ln.add_argument("learn_cmd", nargs="?", default="status",
                    help="status | analyze | ingest-audit | proposals [status] | "
                         "approve <id> | reject <id> [reason] | revert <applied-id> | "
                         "enable | disable")
    ln.add_argument("learn_arg", nargs="?", default=None)
    ln.add_argument("learn_extra", nargs="*", default=[])
    ln.set_defaults(func=_cmd_learn)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.safe:
        # Task 8.3: safe mode via env so every downstream get_settings()
        # (already lru-cached per process) picks it up before any command runs.
        import os
        os.environ["safety__safe_mode"] = "true"
        from jarvis.core.config import reset_settings_cache
        reset_settings_cache()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
