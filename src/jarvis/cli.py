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

    r = sub.add_parser("reflex", help="reflex layer utilities (Task 2.6)")
    r.add_argument("reflex_cmd", nargs="?", default="stats")
    r.set_defaults(func=_cmd_reflex)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
