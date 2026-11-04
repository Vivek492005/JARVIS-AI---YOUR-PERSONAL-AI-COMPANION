"""Onboarding wizard (Master Plan Task 7.6).

Guides a first-time user through: mic test + noise floor → wake-word
calibration → API keys (keyring) → privacy choices → autonomy level →
persona/voice → 3 demo commands → `jarvis doctor` summary.

Design:
- Every step is skippable; progress is persisted so the wizard resumes.
- All I/O (prompting, mic, secrets, doctor) goes through ``StepContext``
  so tests inject fakes — the wizard itself never touches hardware.
- The wizard only *writes* config/secrets; it never sends data anywhere.
"""

from __future__ import annotations

import getpass
import json
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

AUTONOMY_EXPLAIN = {
    0: "L0 — poochho sab kuch: har action se pehle confirmation.",
    1: "L1 — READ auto (default): dekhna free, badalna poochh kar.",
    2: "L2 — READ+REVERSIBLE auto: wapas laaye jaa sakne wale kaam auto.",
    3: "L3 — DESTRUCTIVE bhi auto (SYSTEM tools hamesha poochhenge).",
}

DEMO_COMMANDS = [
    "time batao",
    "notepad kholo",  # dry-run in wizard: goes through the gate only
    "mere baare me kya yaad hai",
]


@dataclass
class StepResult:
    ok: bool
    skipped: bool = False
    detail: str = ""
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StepContext:
    """Everything a step may touch — inject fakes in tests."""

    config: Any  # mutable settings object
    workspace: Path
    ask: Callable[[str, str], str] = lambda q, d="": input(f"{q} [{d}]: ") or d
    ask_secret: Callable[[str], str] = lambda q: getpass.getpass(f"{q}: ")
    store_secret: Callable[[str, str], bool] = lambda k, v: False
    mic_test: Callable[[], Dict[str, Any]] = lambda: {"skipped": True}
    wakeword_test: Callable[[], Dict[str, Any]] = lambda: {"skipped": True}
    run_command: Callable[[str], str] = lambda c: f"(demo) {c}"
    run_doctor: Callable[[], Dict[str, Any]] = lambda: {"ok": True}
    say: Callable[[str], None] = print


@dataclass
class Step:
    id: str
    title: str
    description: str
    run: Callable[[StepContext], StepResult]


def _step_mic(ctx: StepContext) -> StepResult:
    ctx.say("Mic test: 2 second kuch bolo…")
    res = ctx.mic_test()
    if res.get("skipped"):
        return StepResult(ok=False, skipped=True, detail="no mic available")
    rms = float(res.get("rms", 0.0))
    ok = rms > 0.001
    if ok and hasattr(ctx.config, "voice"):
        # Suggest, don't force — the VAD uses a dynamic floor anyway (3.3).
        pass
    return StepResult(ok=ok, detail=f"mic RMS {rms:.4f}")


def _step_wakeword(ctx: StepContext) -> StepResult:
    ctx.say("Wake-word calibration: 'JARVIS' 3 baar bolo…")
    res = ctx.wakeword_test()
    if res.get("skipped"):
        return StepResult(ok=False, skipped=True, detail="no mic available")
    hits = int(res.get("hits", 0))
    return StepResult(ok=hits >= 2, detail=f"{hits}/3 detections")


def _step_api_keys(ctx: StepContext) -> StepResult:
    ctx.say("API keys (khali chhodo to skip — free/local options kaam karenge).")
    saved = []
    for env_name, label in [
        ("RUMIK_API_KEY", "Rumik TTS key"),
        ("TELEGRAM_BOT_TOKEN", "Telegram bot token"),
    ]:
        val = ctx.ask_secret(f"{label} (Enter=skip)").strip()
        if val and ctx.store_secret(env_name, val):
            saved.append(env_name)
    return StepResult(ok=True, detail=f"saved: {', '.join(saved) or 'none'}")


def _step_privacy(ctx: StepContext) -> StepResult:
    ctx.say("Privacy: kaunsi cheez cloud ja sakti hai?")
    choices = {}
    for key, label in [
        ("allow_google_stt", "Speech-to-text (Google)"),
        ("allow_huggingface", "AI brain (HuggingFace)"),
        ("allow_deepseek", "AI brain (DeepSeek)"),
        ("allow_rumik_tts", "Rumik TTS"),
    ]:
        ans = ctx.ask(f"{label} cloud use kare? (haan/nahi)", "haan").strip().lower()
        val = ans in ("haan", "ha", "yes", "y", "")
        choices[key] = val
        if hasattr(ctx.config, "privacy"):
            setattr(ctx.config.privacy, key, val)
    return StepResult(
        ok=True, data=choices, detail="cloud: " + ", ".join(k for k, v in choices.items() if v)
    )


def _step_autonomy(ctx: StepContext) -> StepResult:
    ctx.say("Autonomy level — JARVIS kitna khud kare?")
    for i in range(4):
        ctx.say(f"  {AUTONOMY_EXPLAIN[i]}")
    raw = ctx.ask("Level (0-3)", "1").strip()
    try:
        level = int(raw)
        assert 0 <= level <= 3
    except (ValueError, AssertionError):
        level = 1
    # Config schema: Settings.safety.autonomy_level (SafetyCfg).
    target = getattr(ctx.config, "safety", ctx.config)
    if hasattr(target, "autonomy_level"):
        try:
            target.autonomy_level = level
        except Exception as e:
            logger.debug("onboarding: autonomy_level not set: %s", e)
    return StepResult(ok=True, data={"autonomy_level": level}, detail=AUTONOMY_EXPLAIN[level])


def _step_persona(ctx: StepContext) -> StepResult:
    from jarvis.brain.persona import PERSONA_TEMPLATE

    dest = ctx.workspace / "PERSONA.md"
    if not dest.exists():
        ctx.workspace.mkdir(parents=True, exist_ok=True)
        shutil.copy(PERSONA_TEMPLATE, dest)
        copied = True
    else:
        copied = False
    voice = ctx.ask("TTS voice", "en-IN-NeerjaNeural").strip()
    if hasattr(ctx.config, "voice"):
        ctx.config.voice.neural_voice = voice or "en-IN-NeerjaNeural"
    return StepResult(ok=True, detail=f"persona {'created' if copied else 'kept'}, voice={voice}")


def _step_demos(ctx: StepContext) -> StepResult:
    ctx.say("3 demo commands chala kar dekhte hain:")
    outs = []
    for cmd in DEMO_COMMANDS:
        out = ctx.run_command(cmd)
        outs.append(out)
        ctx.say(f"  > {cmd}\n    {out}")
    return StepResult(ok=True, detail=f"{len(outs)} demos run")


def _step_doctor(ctx: StepContext) -> StepResult:
    res = ctx.run_doctor()
    ok = bool(res.get("ok", True))
    ctx.say("Doctor summary: " + ("sab thik" if ok else "kuch check karo"))
    return StepResult(ok=ok, detail=str(res.get("summary", "")))


STEPS: List[Step] = [
    Step("mic", "Mic test", "Microphone + noise floor check", _step_mic),
    Step("wakeword", "Wake-word", "'JARVIS' calibration", _step_wakeword),
    Step("api_keys", "API keys", "Optional keys -> keyring", _step_api_keys),
    Step("privacy", "Privacy", "Kya cloud jaaye?", _step_privacy),
    Step("autonomy", "Autonomy", "L0-L3 level chuno", _step_autonomy),
    Step("persona", "Persona & voice", "PERSONA.md + TTS voice", _step_persona),
    Step("demos", "Demo", "3 demo commands", _step_demos),
    Step("doctor", "Doctor", "Final health summary", _step_doctor),
]


class OnboardingWizard:
    """Runs STEPS in order, persists progress, resumable."""

    STATE_FILE = ".onboarding.json"

    def __init__(self, ctx: StepContext, state_dir: Optional[Path] = None) -> None:
        self.ctx = ctx
        self.state_dir = state_dir or Path.home() / ".jarvis"
        self.done: Dict[str, Dict[str, Any]] = self._load()

    def _state_path(self) -> Path:
        return self.state_dir / self.STATE_FILE

    def _load(self) -> Dict[str, Dict[str, Any]]:
        try:
            return json.loads(self._state_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save(self) -> None:
        try:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            self._state_path().write_text(json.dumps(self.done, indent=2), encoding="utf-8")
        except OSError as e:
            logger.warning("onboarding state not saved: %s", e)

    @property
    def complete(self) -> bool:
        return all(s.id in self.done for s in STEPS)

    def pending_steps(self) -> List[Step]:
        return [s for s in STEPS if s.id not in self.done]

    def run(self) -> Dict[str, StepResult]:
        results: Dict[str, StepResult] = {}
        for step in self.pending_steps():
            self.ctx.say(f"\n=== {step.title} ===\n{step.description}")
            try:
                res = step.run(self.ctx)
            except Exception as e:  # a step must never kill the wizard
                logger.exception("onboarding step %s failed", step.id)
                res = StepResult(ok=False, detail=f"error: {e}")
            results[step.id] = res
            self.done[step.id] = {"ok": res.ok, "skipped": res.skipped, "detail": res.detail}
            self._save()
            status = "skip" if res.skipped else ("ok" if res.ok else "fail")
            self.ctx.say(f"[{status}] {res.detail}")
        self.ctx.say(
            "\nOnboarding complete!"
            if self.complete
            else "\nKuch steps baaki hain — dobara chalao to resume hoga."
        )
        return results
