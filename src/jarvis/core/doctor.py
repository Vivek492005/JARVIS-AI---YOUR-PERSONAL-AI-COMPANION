"""`jarvis doctor` — diagnostics (Master Plan Task 2.7.2).

Checks: Python/package versions, config validation, disk space, API-key
presence + provider reachability/latency, mic devices, speaker (TTS
engines), camera (optional), permissions. Output is green/yellow/red;
exit code 0 = no reds.

Everything degrades gracefully on non-Windows / headless machines: a
check that cannot run reports yellow ("unknown"), never crashes the run.
"""

from __future__ import annotations

import os
import shutil
import sys
import time
from dataclasses import dataclass
from typing import List

OK, WARN, FAIL = "ok", "warn", "fail"

_GREEN, _YELLOW, _RED, _RESET = "\033[32m", "\033[33m", "\033[31m", "\033[0m"
_DOT = {OK: f"{_GREEN}●{_RESET}", WARN: f"{_YELLOW}●{_RESET}",
        FAIL: f"{_RED}●{_RESET}"}


@dataclass
class Check:
    name: str
    status: str  # ok | warn | fail
    detail: str = ""


def _data_dir() -> str:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        d = os.path.join(base, "jarvis")
    else:
        d = os.path.join(os.path.expanduser("~"), ".jarvis")
    os.makedirs(d, exist_ok=True)
    return d


# -- individual checks -------------------------------------------------------

def check_python() -> Check:
    v = sys.version_info
    ok = (v.major, v.minor) >= (3, 11)
    return Check("python", OK if ok else FAIL,
                 f"{v.major}.{v.minor}.{v.micro} (need >= 3.11)")


def check_packages() -> Check:
    import importlib.metadata as md
    want = {"jarvis-assistant": None, "openai": None, "pydantic": None,
            "pydantic-settings": None, "SpeechRecognition": "speech_recognition",
            "pyttsx3": None, "httpx": None, "fastapi": None}
    missing, versions = [], []
    for dist in want:
        try:
            versions.append(f"{dist} {md.version(dist)}")
        except Exception:
            missing.append(dist)
    if not missing:
        return Check("packages", OK, "; ".join(versions[:4]) + " …")
    # jarvis-assistant itself: missing from pip metadata just means running
    # from a source checkout (doctor is jarvis code, so it is importable).
    notes = []
    if "jarvis-assistant" in missing:
        missing.remove("jarvis-assistant")
        notes.append("jarvis-assistant not pip-installed (source checkout?)")
    # fastapi is optional (server extra); the rest are required.
    optional = {"fastapi"}
    if notes:
        detail = "; ".join(notes)
        if missing:
            detail += f"; missing: {missing}"
        return Check("packages", WARN if set(missing) <= optional else FAIL,
                     detail)
    if set(missing) <= optional:
        return Check("packages", WARN, f"optional missing: {missing}")
    return Check("packages", FAIL, f"missing: {missing}")


def check_config() -> Check:
    try:
        from jarvis.core.config import get_settings
        s = get_settings()
        return Check("config", OK,
                     f"settings.toml loaded (privacy_mode={s.privacy.privacy_mode})")
    except Exception as e:
        return Check("config", FAIL, f"{type(e).__name__}: {e}"[:160])


def check_disk() -> Check:
    try:
        total, used, free = shutil.disk_usage(_data_dir())
        gb = free / (1024 ** 3)
        status = OK if gb > 1.0 else (WARN if gb > 0.2 else FAIL)
        return Check("disk", status, f"{gb:.1f} GB free")
    except Exception as e:
        return Check("disk", WARN, f"unreadable: {e}")


def check_permissions() -> Check:
    d = _data_dir()
    probe = os.path.join(d, ".doctor_probe")
    try:
        with open(probe, "w") as f:
            f.write("ok")
        os.remove(probe)
        return Check("permissions", OK, f"data dir writable ({d})")
    except Exception as e:
        return Check("permissions", FAIL, f"data dir not writable: {e}")


def check_providers() -> List[Check]:
    """API-key presence + reachability + latency per provider."""
    from jarvis.core.secrets import get_secret

    out: List[Check] = []
    specs = [
        ("huggingface", "HUGGINGFACE_API_KEY"),
        ("deepseek", "DEEPSEEK_API_KEY"),
    ]
    for name, env in specs:
        key = get_secret(env)
        if not key:
            out.append(Check(f"provider:{name}", WARN,
                             "no API key — cloud brain unavailable, "
                             "local/heuristic still works"))
            continue
        # Cheap ping: reachability only (no chat call, no spend).
        try:
            import httpx
            base = {"huggingface": "https://router.huggingface.co/v1",
                    "deepseek": "https://api.deepseek.com"}[name]
            t0 = time.perf_counter()
            r = httpx.get(f"{base}/models", timeout=3.0)
            ms = (time.perf_counter() - t0) * 1000.0
            if r.status_code < 500:
                out.append(Check(f"provider:{name}", OK,
                                 f"key set, reachable ({ms:.0f} ms)"))
            else:
                out.append(Check(f"provider:{name}", WARN,
                                 f"key set, HTTP {r.status_code}"))
        except Exception as e:
            out.append(Check(f"provider:{name}", WARN,
                             f"key set, unreachable: {type(e).__name__}"))
    # Ollama (local, optional).
    try:
        import urllib.request
        t0 = time.perf_counter()
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
        ms = (time.perf_counter() - t0) * 1000.0
        out.append(Check("provider:ollama", OK, f"local, up ({ms:.0f} ms)"))
    except Exception:
        out.append(Check("provider:ollama", WARN,
                         "not running (optional local brain)"))
    return out


def check_mic() -> Check:
    try:
        import speech_recognition as sr
        names = sr.Microphone.list_microphone_names()
        if not names:
            return Check("mic", WARN, "no input devices found")
        return Check("mic", OK, f"{len(names)} device(s): {names[0][:40]}")
    except Exception as e:
        return Check("mic", WARN, f"unavailable: {type(e).__name__}")


def check_speaker() -> Check:
    engines = []
    for mod in ("pyttsx3", "edge_tts"):
        try:
            __import__(mod)
            engines.append(mod)
        except ImportError:
            continue
    if engines:
        return Check("speaker", OK, f"TTS engines: {', '.join(engines)}")
    return Check("speaker", WARN, "no TTS engine importable")


def check_camera() -> Check:
    try:
        import cv2  # noqa: F401
        return Check("camera", OK, "opencv available (optional)")
    except ImportError:
        return Check("camera", WARN, "opencv not installed (optional)")


def check_metrics() -> Check:
    from jarvis.core.metrics import MetricsRecorder
    rows = MetricsRecorder().tail(50)
    if not rows:
        return Check("metrics", WARN, "no utterances recorded yet")
    llm = [r for r in rows if r.get("path") == "llm" and r.get("total_ms")]
    if llm:
        avg = sum(float(r["total_ms"]) for r in llm) / len(llm)
        return Check("metrics", OK,
                     f"{len(rows)} turns today, LLM avg {avg:.0f} ms")
    return Check("metrics", OK, f"{len(rows)} turns today (all reflex)")


# -- runner -------------------------------------------------------------------

def all_checks() -> List[Check]:
    checks: List[Check] = [
        check_python(),
        check_packages(),
        check_config(),
        check_disk(),
        check_permissions(),
    ]
    checks.extend(check_providers())
    checks += [check_mic(), check_speaker(), check_camera(), check_metrics()]
    return checks


def run_doctor(verbose: bool = True) -> int:
    """Run all checks, print the report, return exit code (0 = no reds)."""
    checks = all_checks()
    if verbose:
        print("jarvis doctor\n")
        width = max(len(c.name) for c in checks)
        for c in checks:
            print(f"  {_DOT[c.status]} {c.name:<{width}}  {c.detail}")
        print()
        n_fail = sum(1 for c in checks if c.status == FAIL)
        n_warn = sum(1 for c in checks if c.status == WARN)
        if n_fail:
            print(f"{_RED}{n_fail} failing{_RESET}, {n_warn} warnings")
        elif n_warn:
            print(f"{_YELLOW}all good{_RESET}, {n_warn} warnings")
        else:
            print(f"{_GREEN}all checks green{_RESET}")
    return 1 if any(c.status == FAIL for c in checks) else 0
