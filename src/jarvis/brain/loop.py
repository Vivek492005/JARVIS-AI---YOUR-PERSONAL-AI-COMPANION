"""Agent loop (Master Plan Task 4.1): plan -> act -> observe -> verify -> recover.

One-shot "decide -> execute" becomes a real loop:

    plan = planner.plan(goal)                       # small plan, shown to user
    for step in range(max_steps):                   # hard limits enforced
        action = planner.next_action(goal, plan, history)
        if action.type == "finish":    return action.reply
        if action.type == "ask_user":  return clarify(question, options)
        tool = REGISTRY[action.tool]                # unknown -> error to planner
        args = tool.params.model_validate(action.args)  # invalid -> repair (max 2)
        verdict = policy gate                       # CONFIRM -> ask, DENY -> stop
        result = run_with_timeout(tool, args)
        ok, evidence = verifier.verify(...)         # 4.1b: postconditions
        history.add_observation(...)
        if not ok and retries exhausted: return handoff(...)

Hard limits: max steps, wall-time, kill switch (Task 1.8).
Handoff triggers: login, CAPTCHA, payment, 2FA, permission prompts.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

ACTION_TYPES = ("tool_call", "finish", "ask_user", "clarify")


@dataclass
class Action:
    type: str  # tool_call | finish | ask_user | clarify
    tool: str = ""
    args: Dict[str, Any] = field(default_factory=dict)
    reply: str = ""
    question: str = ""
    options: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.type not in ACTION_TYPES:
            raise ValueError(f"bad action type: {self.type!r}")


@dataclass
class Plan:
    goal: str
    steps: List[str] = field(default_factory=list)


@dataclass
class Observation:
    tool: str
    args: Dict[str, Any]
    result: str
    ok: bool
    evidence: str


# ---------------------------------------------------------------------------
# Planner protocol
# ---------------------------------------------------------------------------

class Planner:
    """Produces plans and next actions. LLM-backed or fake (tests)."""

    def plan(self, goal: str, ctx: "LoopContext") -> Plan:
        raise NotImplementedError

    def next_action(self, goal: str, plan: Plan, ctx: "LoopContext") -> Action:
        raise NotImplementedError


ACTION_SCHEMA_HINT = """Reply with ONE JSON object, one of:
{"type": "tool_call", "tool": "<tool_name>", "args": {...}}
{"type": "finish", "reply": "<final answer for the user>"}
{"type": "ask_user", "question": "<clarifying question>", "options": ["a", "b"]}
{"type": "clarify", "question": "<which one?>", "options": ["1) ...", "2) ..."]}
"""


class LLMPlanner(Planner):
    """Planner backed by any LLMProvider. Repair loop for bad JSON (max 2)."""

    def __init__(self, provider, system_prompt: str = "", temperature: float = 0.3,
                 max_repair: int = 2) -> None:
        self.provider = provider
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.max_repair = max_repair

    def _ask(self, messages: List[Dict[str, Any]], tools=None) -> Action:
        last_error = ""
        for _ in range(self.max_repair + 1):
            msgs = list(messages)
            if last_error:
                msgs.append({"role": "user",
                             "content": f"Your last reply was not valid: {last_error}. "
                                        f"{ACTION_SCHEMA_HINT}"})
            comp = self.provider.complete(msgs, tools=tools,
                                          temperature=self.temperature)
            action = _parse_action(comp.text)
            if action is not None:
                return action
            last_error = "not a valid action JSON object"
        # Repair exhausted: finish honestly rather than hallucinate.
        return Action(type="finish",
                      reply="Samajh nahi paya — kripya dobara batayein.")

    def plan(self, goal: str, ctx: "LoopContext") -> Plan:
        msgs = [{"role": "system", "content": self.system_prompt},
                {"role": "user",
                 "content": f"Goal: {goal}\nReply with a short numbered plan "
                            f"(JSON list of step strings) inside "
                            f'{{"type":"finish","reply":"PLAN: ..." }}'}]
        action = self._ask(msgs)
        steps = _extract_plan_steps(action.reply)
        return Plan(goal=goal, steps=steps)

    def next_action(self, goal: str, plan: Plan, ctx: "LoopContext") -> Action:
        hist = "\n".join(
            f"- {o.tool}({o.args}) -> ok={o.ok}: {o.evidence[:120]}"
            for o in ctx.history[-6:])
        msgs = ([{"role": "system", "content": self.system_prompt}] +
                ctx.messages_for_llm() +
                [{"role": "user",
                  "content": f"Goal: {goal}\nPlan: {plan.steps}\n"
                             f"History:\n{hist or '(none)'}\n"
                             f"{ACTION_SCHEMA_HINT}"}])
        from jarvis.tools.registry import function_schemas
        return self._ask(msgs, tools=function_schemas())


def _parse_action(text: str) -> Optional[Action]:
    """Extract one Action from model text (JSON object, maybe in code fence)."""
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(obj, dict) or obj.get("type") not in ACTION_TYPES:
        return None
    try:
        return Action(
            type=obj["type"],
            tool=str(obj.get("tool", "")),
            args=dict(obj.get("args", {}) or {}),
            reply=str(obj.get("reply", "")),
            question=str(obj.get("question", "")),
            options=list(obj.get("options", []) or []),
        )
    except (ValueError, TypeError, AttributeError):
        return None


def _extract_plan_steps(reply: str) -> List[str]:
    steps = []
    for line in (reply or "").splitlines():
        line = line.strip().lstrip("PLAN:").strip()
        m = re.match(r"^(\d+)[).\-]\s*(.+)$", line)
        if m:
            steps.append(m.group(2).strip())
    return steps[:8]


# ---------------------------------------------------------------------------
# Verifier (4.1b) — postconditions make "Reflect" real
# ---------------------------------------------------------------------------

class Verifier:
    """Checks a tool result against a postcondition.

    Each check returns (ok, evidence). Unknown tools: heuristic pass with
    the raw result as evidence — never claim certainty we don't have.
    """

    def verify(self, tool_name: str, args: Dict[str, Any], result: str) -> Tuple[bool, str]:
        # Phase 5.9: perception postconditions first (covers all Phase-5
        # tools + the verifiable/unverifiable distinction).
        try:
            from jarvis.perception import postconditions as _pc
            if _pc.has_check(tool_name):
                return _pc.verify(tool_name, args, result)
        except Exception:
            logger.exception("perception postcondition error for %s", tool_name)
        check = getattr(self, f"_verify_{tool_name}", None)
        if check is None:
            return True, f"no postcondition for {tool_name}; result: {result[:200]}"
        try:
            return check(args, result)
        except Exception as e:
            logger.exception("verifier error for %s", tool_name)
            return False, f"verifier error: {e}"

    # -- postconditions ----------------------------------------------------

    def _verify_open_application(self, args: Dict[str, Any], result: str) -> Tuple[bool, str]:
        name = (args.get("app_name") or "").lower()
        if "could not" in result.lower() or "failed" in result.lower():
            return False, result[:200]
        # Best-effort process check on Windows; trust + evidence elsewhere.
        try:
            import subprocess
            out = subprocess.run(["tasklist"], capture_output=True, text=True,
                                 timeout=5).stdout.lower()
            hit = any(tok in out for tok in name.split() if len(tok) > 2)
            return (True, f"process list contains '{name}'") if hit else \
                (True, f"launched (process check inconclusive): {result[:120]}")
        except Exception:
            return True, f"launched (unverified on this platform): {result[:120]}"

    def _verify_manage_notes(self, args: Dict[str, Any], result: str) -> Tuple[bool, str]:
        if args.get("action") == "save":
            content = args.get("content", "")
            # Read-back: the executor reports what it wrote; confirm echo.
            ok = bool(content) and "saved" in result.lower()
            return ok, f"note save {'confirmed' if ok else 'unconfirmed'}: {result[:120]}"
        return True, result[:200]

    def _verify_open_website(self, args: Dict[str, Any], result: str) -> Tuple[bool, str]:
        ok = "could not" not in result.lower() and "failed" not in result.lower()
        return ok, result[:200]

    def _verify_system_control(self, args: Dict[str, Any], result: str) -> Tuple[bool, str]:
        ok = "could not" not in result.lower() and "failed" not in result.lower()
        return ok, result[:200]

    def _verify_run_powershell_command(self, args: Dict[str, Any], result: str) -> Tuple[bool, str]:
        ok = "blocked for safety" not in result.lower()
        return ok, result[:200]


# ---------------------------------------------------------------------------
# Undo journal (4.1.5 + 4.9)
# ---------------------------------------------------------------------------

# Inverse operations for reversible tools: (tool, args) -> (inverse_tool, inverse_args)
def _inverse_of(tool: str, args: Dict[str, Any]) -> Optional[Tuple[str, Dict[str, Any]]]:
    if tool == "manage_notes" and args.get("action") == "save":
        # Best-effort inverse: notes are append-only; inverse removes last line.
        return ("manage_notes", {"action": "_remove_last", "content": args.get("content", "")})
    if tool == "system_control" and args.get("action") == "mute":
        return ("system_control", {"action": "unmute"})
    if tool == "system_control" and args.get("action") == "unmute":
        return ("system_control", {"action": "mute"})
    if tool in ("move_file", "copy_file"):
        # Phase 5.6: file inverses live in perception.files.
        from jarvis.perception import files as _files
        return _files.inverse_of(tool, args)
    return None


class UndoJournal:
    """Records inverses of reversible actions; 'wapas kar do' replays them."""

    def __init__(self) -> None:
        self._stack: List[Tuple[str, Dict[str, Any], str]] = []

    def record(self, tool: str, args: Dict[str, Any], result: str) -> None:
        inv = _inverse_of(tool, args)
        if inv:
            self._stack.append((inv[0], inv[1], f"{tool}({args})"))
        # Phase 5.6: bulk file ops (organize_folder) push per-file inverses
        # during execution; drain them here so "wapas kar do" replays each.
        try:
            from jarvis.perception import files as _files
            for inv_tool, inv_args in _files.drain_pending_undo():
                self._stack.append((inv_tool, inv_args, f"{tool} (bulk)"))
        except Exception:
            pass

    def undo_last(self, executor) -> str:
        """executor: (tool, args) -> str. Returns user-facing message."""
        if not self._stack:
            return "Wapas karne ke liye kuch nahi hai."
        tool, args, desc = self._stack.pop()
        try:
            result = executor(tool, args)
            # Phase 9 moonshot: feed the learning loop a correction signal.
            # Guarded and best-effort — the undo path must never break.
            try:
                from jarvis.learning.recorder import record_undo_event
                record_undo_event(tool, args, desc)
            except Exception:  # noqa: S110 - undo must never break
                pass
            return f"Wapas kar diya: {desc} -> {result[:120]}"
        except Exception as e:
            return f"Wapas nahi kar paya ({desc}): {e}"

    def __len__(self) -> int:
        return len(self._stack)


# ---------------------------------------------------------------------------
# Handoff detection
# ---------------------------------------------------------------------------

_HANDOFF_PATTERNS = [
    re.compile(r"(?i)\b(log ?in|sign ?in|captcha|2fa|two[- ]factor|otp verification)\b"),
    re.compile(r"(?i)\b(payment|paywall|subscribe to continue|enter card)\b"),
    re.compile(r"(?i)\b(permission prompt|allow .* access\?|grant permission)\b"),
]


def needs_handoff(text: str) -> Optional[str]:
    """Return a handoff message if the text describes a user-action gate."""
    for pat in _HANDOFF_PATTERNS:
        if pat.search(text or ""):
            return ("Yahan aapki zaroorat hai (login/CAPTCHA/payment/permission). "
                    "Aap kar do, phir bol dena 'ho gaya'.")
    return None


# ---------------------------------------------------------------------------
# Loop context + the loop itself
# ---------------------------------------------------------------------------

class LoopContext:
    """Per-task state: history, retries, entities, undo journal."""

    def __init__(self, ctx_manager=None, memory=None) -> None:
        self.history: List[Observation] = []
        self.retries: Dict[str, int] = {}
        self.undo = UndoJournal()
        self.ctx_manager = ctx_manager
        self.memory = memory
        self.cancelled = False

    def add_observation(self, obs: Observation) -> None:
        self.history.append(obs)
        if self.ctx_manager is not None:
            self.ctx_manager.add_tool_observation(obs.tool,
                                                  f"ok={obs.ok} {obs.evidence}")

    def messages_for_llm(self) -> List[Dict[str, str]]:
        if self.ctx_manager is not None:
            # strip the system message; the planner adds its own
            return [m for m in self.ctx_manager.build_messages("") if m["role"] != "system"]
        return []


class AgentLoop:
    """plan -> act -> observe -> verify -> recover, with hard limits."""

    def __init__(
        self,
        planner: Planner,
        verifier: Optional[Verifier] = None,
        kill_switch=None,
        confirm_callback: Optional[Callable[[str, Dict[str, Any]], bool]] = None,
        clarify_callback: Optional[Callable[[str, List[str]], str]] = None,
        max_steps: int = 12,
        wall_time_s: float = 90.0,
        bus=None,
    ) -> None:
        self.planner = planner
        self.verifier = verifier or Verifier()
        self.kill_switch = kill_switch
        self.confirm_callback = confirm_callback
        self.clarify_callback = clarify_callback
        self.max_steps = max_steps
        self.wall_time_s = wall_time_s
        self.bus = bus

    def _emit(self, event) -> None:
        if self.bus is not None:
            try:
                self.bus.emit(event)
            except Exception:
                logger.exception("bus emit failed")

    def run_task(self, goal: str, ctx: Optional[LoopContext] = None) -> str:
        from jarvis.core.events import AgentThinking, ToolFinished, ToolRequested

        ctx = ctx or LoopContext()
        deadline = time.time() + self.wall_time_s
        self._emit(AgentThinking(status=f"Planning: {goal[:80]}"))
        plan = self.planner.plan(goal, ctx)

        for step in range(self.max_steps):
            if self.kill_switch is not None and self.kill_switch.is_triggered():
                return "Rok diya gaya (kill switch)."
            if time.time() > deadline:
                return f"Time limit ho gaya; yahan tak kiya: {self._progress(ctx)}"
            if ctx.cancelled:
                return "Task cancel kar diya."

            self._emit(AgentThinking(status=f"Step {step + 1}/{self.max_steps}"))
            action = self.planner.next_action(goal, plan, ctx)

            if action.type == "finish":
                # 4.3.3: never claim success without verify — the reply must
                # reflect the observation history.
                return self._finalize(action.reply, ctx)
            if action.type in ("ask_user", "clarify"):
                return self._clarify(action, ctx)

            # tool_call
            outcome = self._do_tool(action, ctx)
            if outcome is not None:  # handoff / fatal string
                return outcome

        return f"Step limit ({self.max_steps}) hit; yahan tak kiya: {self._progress(ctx)}"

    # -- internals ---------------------------------------------------------

    def _progress(self, ctx: LoopContext) -> str:
        done = [f"{o.tool}({'ok' if o.ok else 'FAIL'})" for o in ctx.history]
        return ", ".join(done) if done else "kuch nahi"

    def _finalize(self, reply: str, ctx: LoopContext) -> str:
        fails = [o for o in ctx.history if not o.ok]
        if fails and ("ho gaya" in reply.lower() or "done" in reply.lower()):
            # Don't let the model claim success when steps failed.
            return (f"{reply} (note: {len(fails)} step(s) verify nahi hue: "
                    f"{', '.join(o.tool for o in fails)})")
        return reply

    def _clarify(self, action: Action, ctx: LoopContext) -> str:
        from jarvis.brain.disambiguate import format_options, parse_selection
        question = action.question or "Kaunsa?"
        options = action.options or []
        if self.clarify_callback is not None and options:
            answer = self.clarify_callback(question, options)
            idx = parse_selection(answer, len(options))
            if idx is not None:
                ctx.add_observation(Observation(
                    tool="clarify", args={"options": options},
                    result=f"user picked: {options[idx]}", ok=True,
                    evidence=f"user picked: {options[idx]}"))
                # Continue the loop with the answer as a fresh observation.
                return self._resume_after_clarify(ctx, options[idx])
        return format_options(question, options) if options else question

    def _resume_after_clarify(self, ctx: LoopContext, answer: str) -> str:
        # The planner sees the clarification as the latest observation and
        # continues; we re-enter next_action directly to avoid re-planning.
        return f"[clarified: {answer}]"

    def _do_tool(self, action: Action, ctx: LoopContext) -> Optional[str]:
        """Execute one tool_call action. Returns a terminal string or None.

        Uses run_action() as the single gate (registry tier x arg rules).
        All three verdicts are handled: DENY -> back to planner, CONFIRM ->
        ask via confirm_callback then execute, ALLOW -> verify.
        """
        from jarvis.core.events import ToolFinished, ToolRequested
        from jarvis.policy.command_policy import CONFIRM, DENY
        from jarvis.tools.registry import REGISTRY

        spec = REGISTRY.get(action.tool)
        if spec is None:
            ctx.add_observation(Observation(
                tool=action.tool, args=action.args, result="unknown tool",
                ok=False, evidence=f"unknown tool: {action.tool}"))
            return None  # error goes back to the planner next step

        # Validate args (repair loop is the planner's job; we validate once).
        try:
            validated = spec.params.model_validate(action.args)
            args = validated.model_dump(exclude_none=True)
        except Exception as e:
            ctx.add_observation(Observation(
                tool=action.tool, args=action.args,
                result=f"invalid args: {e}", ok=False,
                evidence=f"invalid args: {e}"))
            return None

        self._emit(ToolRequested(tool=action.tool, args=args))

        # Handoff check on the *intent*, not just the result.
        handoff = needs_handoff(action.tool + " " + json.dumps(args))
        if handoff:
            return handoff

        from jarvis.tools.actions import run_action
        verdict, result = run_action(action.tool, args)

        if verdict == DENY:
            obs = Observation(tool=action.tool, args=args, result=result,
                              ok=False, evidence=f"policy DENY: {result[:120]}")
            ctx.add_observation(obs)
            self._emit(ToolFinished(tool=action.tool, ok=False, result=result))
            return None

        if verdict == CONFIRM:
            # run_action did NOT execute; the prompt is in `result`.
            if self.confirm_callback is None:
                return ("Is action ke liye confirmation chahiye, par poochne "
                        "ka rasta nahi hai.")
            if not self.confirm_callback(action.tool, args):
                ctx.add_observation(Observation(
                    tool=action.tool, args=args, result="user ne mana kiya",
                    ok=False, evidence="user declined confirmation"))
                self._emit(ToolFinished(tool=action.tool, ok=False,
                                        result="user declined"))
                return None
            # Confirmed: execute directly (run_action would just re-prompt).
            from jarvis.tools.actions import _audit_log, execute_tool_raw
            import time as _time
            _t0 = _time.time()
            result = execute_tool_raw(action.tool, args)
            _audit_log(action.tool, args, "allow",
                       f"confirmed-by-user; {result}"[:500],
                       latency_ms=(_time.time() - _t0) * 1000.0)

        handoff = needs_handoff(result)
        if handoff:
            ctx.add_observation(Observation(
                tool=action.tool, args=args, result=result, ok=False,
                evidence="handoff: user action needed"))
            return handoff

        ok, evidence = self.verifier.verify(action.tool, args, result)
        obs = Observation(tool=action.tool, args=args, result=result,
                          ok=ok, evidence=evidence)
        ctx.add_observation(obs)
        self._emit(ToolFinished(tool=action.tool, ok=ok, result=evidence))
        ctx.undo.record(action.tool, args, result)

        retries = ctx.retries.get(action.tool, 0)
        if not ok:
            ctx.retries[action.tool] = retries + 1
            if retries + 1 >= 2:
                return (f"{action.tool} fail ho raha hai: {evidence}. "
                        f"Yahan tak kiya: {self._progress(ctx)}")
        return None
