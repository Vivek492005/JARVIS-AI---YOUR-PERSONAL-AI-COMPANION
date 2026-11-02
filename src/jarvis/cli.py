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
import logging
import sys

logger = logging.getLogger("jarvis.cli")


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


def _cmd_skill(args) -> int:
    from jarvis.brain.skills import load_all, load_manifest
    from jarvis.brain.skills.scaffold import new_skill
    from jarvis.brain.skills.trust import TrustLevel

    skills_dir = _skills_dir()
    cmd, arg = args.skill_cmd, args.skill_arg
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
    print("usage: jarvis skill [list|new|enable|disable]", file=sys.stderr)
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
                    help="list | new <name> | enable <name> | disable <name>")
    sk.add_argument("skill_arg", nargs="?", default=None)
    sk.set_defaults(func=_cmd_skill)

    mem = sub.add_parser("memory", help="memory controls (Task 4.4)")
    mem.add_argument("memory_cmd", nargs="?", default="list",
                     help="list | forget <text> | export | wipe | remember <text>")
    mem.add_argument("memory_arg", nargs="?", default=None)
    mem.set_defaults(func=_cmd_memory)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
