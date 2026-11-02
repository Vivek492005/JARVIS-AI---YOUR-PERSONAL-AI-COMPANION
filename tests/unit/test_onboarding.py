"""Tests for the onboarding wizard (Task 7.6). All I/O is faked."""

import json
import sys
from types import SimpleNamespace


sys.path.insert(0, "src")

from jarvis.onboarding.wizard import (
    AUTONOMY_EXPLAIN,
    STEPS,
    OnboardingWizard,
    StepContext,
)


def _ctx(**over):
    answers = over.pop("answers", {})
    secrets = {}
    said = []
    base = dict(
        config=SimpleNamespace(
            privacy=SimpleNamespace(),
            safety=SimpleNamespace(autonomy_level=1),
            voice=SimpleNamespace(neural_voice="en-IN-NeerjaNeural"),
            memory_workspace="",
        ),
        workspace=None,  # set per-test with tmp_path
        ask=lambda q, d="": answers.get(q, d),
        ask_secret=lambda q: answers.get("secret:" + q, ""),
        store_secret=lambda k, v: secrets.__setitem__(k, v) or True,
        mic_test=lambda: {"rms": 0.05},
        wakeword_test=lambda: {"hits": 3},
        run_command=lambda c: f"ok: {c}",
        run_doctor=lambda: {"ok": True, "summary": "all green"},
        say=said.append,
    )
    base.update(over)
    ctx = StepContext(**{k: v for k, v in base.items()
                         if k in StepContext.__dataclass_fields__})
    ctx._secrets = secrets
    ctx._said = said
    return ctx


def test_eight_steps_in_plan_order():
    assert [s.id for s in STEPS] == ["mic", "wakeword", "api_keys", "privacy",
                                     "autonomy", "persona", "demos", "doctor"]


def test_full_run_all_ok(tmp_path):
    ctx = _ctx(workspace=tmp_path)
    wiz = OnboardingWizard(ctx, state_dir=tmp_path / "state")
    results = wiz.run()
    assert wiz.complete
    assert all(r.ok for r in results.values())
    # persona template copied
    assert (tmp_path / "PERSONA.md").exists()
    # state persisted
    state = json.loads((tmp_path / "state" / ".onboarding.json").read_text())
    assert set(state) == {s.id for s in STEPS}


def test_resume_skips_done_steps(tmp_path):
    ctx = _ctx(workspace=tmp_path)
    wiz = OnboardingWizard(ctx, state_dir=tmp_path / "state")
    wiz.run()
    # second run: nothing pending
    wiz2 = OnboardingWizard(ctx, state_dir=tmp_path / "state")
    assert wiz2.pending_steps() == []
    assert wiz2.run() == {}


def test_mic_failure_does_not_kill_wizard(tmp_path):
    ctx = _ctx(workspace=tmp_path, mic_test=lambda: {"rms": 0.0})
    wiz = OnboardingWizard(ctx, state_dir=tmp_path / "state")
    results = wiz.run()
    assert results["mic"].ok is False
    assert wiz.complete  # failed steps still count as done


def test_step_exception_is_contained(tmp_path):
    def boom():
        raise RuntimeError("mic exploded")
    ctx = _ctx(workspace=tmp_path, mic_test=boom)
    wiz = OnboardingWizard(ctx, state_dir=tmp_path / "state")
    results = wiz.run()
    assert results["mic"].ok is False
    assert "error" in results["mic"].detail
    assert wiz.complete


def test_autonomy_level_written_to_config(tmp_path):
    ctx = _ctx(workspace=tmp_path,
               answers={"Level (0-3)": "2"})
    wiz = OnboardingWizard(ctx, state_dir=tmp_path / "state")
    wiz.run()
    assert ctx.config.safety.autonomy_level == 2


def test_autonomy_invalid_falls_back_to_1(tmp_path):
    ctx = _ctx(workspace=tmp_path,
               answers={"Level (0-3)": "banana"})
    wiz = OnboardingWizard(ctx, state_dir=tmp_path / "state")
    results = wiz.run()
    assert results["autonomy"].data["autonomy_level"] == 1


def test_privacy_choices_written(tmp_path):
    ctx = _ctx(workspace=tmp_path, answers={
        "Speech-to-text (Google) cloud use kare? (haan/nahi)": "nahi",
    })
    wiz = OnboardingWizard(ctx, state_dir=tmp_path / "state")
    wiz.run()
    assert ctx.config.privacy.allow_google_stt is False
    assert ctx.config.privacy.allow_huggingface is True


def test_api_keys_stored_via_secrets(tmp_path):
    ctx = _ctx(workspace=tmp_path, answers={
        "secret:Rumik TTS key (Enter=skip)": "rk-test-123",
        "secret:Telegram bot token (Enter=skip)": "",
    })
    wiz = OnboardingWizard(ctx, state_dir=tmp_path / "state")
    wiz.run()
    assert ctx._secrets == {"RUMIK_API_KEY": "rk-test-123"}


def test_demos_run_three_commands(tmp_path):
    ran = []
    ctx = _ctx(workspace=tmp_path, run_command=lambda c: ran.append(c) or "ok")
    wiz = OnboardingWizard(ctx, state_dir=tmp_path / "state")
    wiz.run()
    assert len(ran) == 3


def test_autonomy_explain_covers_all_levels():
    assert set(AUTONOMY_EXPLAIN) == {0, 1, 2, 3}
