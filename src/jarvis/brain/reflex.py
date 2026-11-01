"""Reflex layer — System-1 fast path (Master Plan Task 2.6).

Trivial commands (volume, open site/app, time, …) never touch the LLM:
normalized text → regex/fuzzy match → **policy-gated** ToolSpec call.
Zero network, free, offline-capable.

Rules live as data in :py:mod:`jarvis.legacy.rule_commands` (AST-extracted
from the legacy voice table). Confidence: regex hit = 1.0, fuzzy hit =
score/100. The router (brain/router.py) only takes the reflex path at
confidence ≥ 0.85; anything lower goes to the LLM (System-2).

Hinglish normalization: common Hindi verbs map to their English
counterparts (``kholo`` → ``open``), filler words (``bhai``, ``yaar``,
``please``) are stripped, Hindi number words become digits.
"""

from __future__ import annotations

import ast
import json
import logging
import operator
import os
import random
import re
import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

# Hindi/Hinglish verbs -> the English verb the patterns were written for.
HINGLISH_VERBS = {
    "kholo": "open", "khol": "open", "kholde": "open", "khol de": "open", "khol do": "open",
    "band karo": "close", "band kar": "close", "band karde": "close",
    "chalao": "play", "chala": "play", "chala do": "play",
    "dikhao": "show", "dikha": "show",
    "batao": "tell", "bata": "tell",
    "lagao": "set",
    "nikalo": "find",
    "dhoondo": "search",
    "likho": "write",
    # Volume / common auxiliaries (eval 4.7: these never matched).
    "badhao": "up", "badhaiye": "up", "tez karo": "up", "tez kar": "up",
    "kam karo": "down", "kam kar": "down", "ghatao": "down",
    "dheemi karo": "down", "dheeme karo": "down",
    "lo": "take", "le": "take",
    "kar do": "", "kar de": "",
}

# Filler words stripped from the edges (never from the middle — "bhai" can
# be part of a query like "bhai dooj").
FILLER_WORDS = {
    "bhai", "yaar", "please", "pls", "zara", "arre", "suno", "sun",
    "hello", "hey", "na", "to", "ji", "han", "haan",
}

# Hindi number words -> digits (plan §2.6: "numbers").
HINDI_NUMBERS = {
    "ek": "1", "do": "2", "teen": "3", "chaar": "4", "paanch": "5",
    "chhah": "6", "saat": "7", "aath": "8", "nau": "9", "das": "10",
}

_FUZZY_THRESHOLD = 78  # legacy parity; router requires >= 0.85 anyway


def normalize(text: str) -> str:
    """Normalize an utterance for reflex matching."""
    t = (text or "").lower().strip()
    t = re.sub(r"\s+", " ", t)
    # Multi-word verbs first ("khol do" before "khol").
    for src in sorted(HINGLISH_VERBS, key=len, reverse=True):
        t = re.sub(r"\b" + re.escape(src) + r"\b", HINGLISH_VERBS[src], t)
    words = t.split()
    for num_word, digit in HINDI_NUMBERS.items():
        words = [digit if w == num_word else w for w in words]
    # Strip filler words from both edges only.
    while words and words[0] in FILLER_WORDS:
        words.pop(0)
    while words and words[-1] in FILLER_WORDS:
        words.pop()
    # Hindi is verb-final ("chrome kholo" -> "chrome open"); rules expect
    # English verb-first order, so move a trailing action verb to the front.
    # (Eval 4.7 found: verb-final utterances never matched.)
    # "up"/"down" are complements, not verbs — "volume up" is already
    # correct order, so they are excluded from fronting.
    _FRONTABLE_VERBS = frozenset(
        v for v in HINGLISH_VERBS.values() if v not in ("up", "down"))
    if (len(words) >= 2 and words[-1] in _FRONTABLE_VERBS
            and words[0] not in _FRONTABLE_VERBS):
        words = [words[-1]] + words[:-1]
    return " ".join(words)


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------

_TEMPLATE_RE = re.compile(r"\{group(\d+)(?:\|([^}]+))?\}")


def _clean_query(q: str) -> str:
    """Light cleanup for captured queries (mirrors the legacy handlers)."""
    q = (q or "").strip()
    for prefix in ("play ", "search youtube for ", "youtube search ",
                   "google for ", "google ", "for ", "the file ", "file ",
                   "a file "):
        if q.lower().startswith(prefix):
            q = q[len(prefix):].strip()
    for suffix in (" on youtube", " in youtube", " youtube"):
        if q.lower().endswith(suffix):
            q = q[: -len(suffix)].strip()
    return q


def render_template(template: Any, groups: List[str]) -> Any:
    """Render ``{groupN}``, ``{groupN|urlencode}`` and ``{groupN|default:X}``."""
    if not isinstance(template, str):
        return template

    def _sub(m: re.Match) -> str:
        idx = int(m.group(1)) - 1
        filt = m.group(2)
        val = _clean_query(groups[idx]) if 0 <= idx < len(groups) else ""
        if filt == "urlencode":
            return urllib.parse.quote_plus(val)
        if filt and filt.startswith("default:"):
            return val if val else filt[len("default:"):]
        return val

    return _TEMPLATE_RE.sub(_sub, template)


# ---------------------------------------------------------------------------
# Compute rules (no tool call, no side effects)
# ---------------------------------------------------------------------------

def _compute(kind: str, groups: List[str], rng: random.Random) -> str:
    now = datetime.now()
    if kind == "time":
        return f"The current time is {now.strftime('%I:%M %p')}"
    if kind == "date":
        return f"Today is {now.strftime('%A, %B %d, %Y')}"
    if kind == "day":
        return f"Today is {now.strftime('%A')}"
    if kind == "joke":
        from jarvis.legacy.rule_commands import JOKES
        return rng.choice(JOKES)
    if kind == "coin":
        return f"It's {rng.choice(['Heads', 'Tails'])}!"
    if kind == "dice":
        return f"You rolled a {rng.randint(1, 6)}!"
    if kind == "calc":
        return _calculate(groups[0] if groups else "")
    return ""


def _calculate(expr: str) -> str:
    """Strict AST arithmetic evaluator (moved from the legacy engine).

    Only arithmetic nodes; capped input length, depth and exponent size
    (the old eval() allowed CPU-DoS via 9^9^9^9 — A-07).
    """
    expr = (expr or "").strip()
    if len(expr) > 100:
        return "Sorry, that expression is too long."
    sanitized = re.sub(r"[^0-9\+\-\*\/\%\(\)\.\^ ]", "", expr)
    sanitized = sanitized.replace("^", "**")
    if not sanitized.strip():
        return f"Sorry, could not calculate {expr}"
    _binops = {ast.Add: operator.add, ast.Sub: operator.sub,
               ast.Mult: operator.mul, ast.Div: operator.truediv,
               ast.Mod: operator.mod, ast.Pow: operator.pow}
    _unaryops = {ast.UAdd: operator.pos, ast.USub: operator.neg}

    def _eval(node, depth=0):
        if depth > 64:
            raise ValueError("expression too deep")
        if isinstance(node, ast.Expression):
            return _eval(node.body, depth + 1)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _binops:
            left = _eval(node.left, depth + 1)
            right = _eval(node.right, depth + 1)
            if type(node.op) is ast.Pow and (abs(right) > 100 or abs(left) > 10 ** 6):
                raise ValueError("exponent too large")
            return _binops[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _unaryops:
            return _unaryops[type(node.op)](_eval(node.operand, depth + 1))
        raise ValueError("unsupported expression")

    try:
        result = _eval(ast.parse(sanitized, mode="eval"))
        return f"{expr} is {result}"
    except Exception:
        return f"Sorry, could not calculate {expr}"


# ---------------------------------------------------------------------------
# Matcher
# ---------------------------------------------------------------------------

@dataclass
class ReflexHit:
    rule_id: str
    tool: Optional[str]
    args: Dict[str, Any]
    reply: Any  # str | list[str] | None — rendered reply template
    compute: Optional[str]
    confidence: float
    groups: List[str] = field(default_factory=list)

    def render_reply(self, rng: random.Random) -> str:
        if self.compute:
            return _compute(self.compute, self.groups, rng)
        reply = self.reply
        if isinstance(reply, list):
            reply = rng.choice(reply)
        return render_template(reply or "", self.groups)

    def render_args(self) -> Dict[str, Any]:
        return {k: render_template(v, self.groups)
                for k, v in (self.args or {}).items()}


class ReflexMatcher:
    """Regex/fuzzy matcher over the extracted rule data."""

    def __init__(self, rules=None, stats: Optional["ReflexStats"] = None,
                 rng: Optional[random.Random] = None) -> None:
        if rules is None:
            from jarvis.legacy.rule_commands import RULES
            rules = RULES
        self._rules = rules
        # Pre-compile patterns once.
        self._compiled = [
            (rule, [re.compile(p, re.IGNORECASE) for p in rule["patterns"]])
            for rule in rules
        ]
        # Pre-expand fuzzy alternatives once (regex stage handles the
        # parameterized patterns; fuzzy only sees literal alternatives).
        self._fuzzy_alts: List[tuple] = []
        for rule in rules:
            for pattern in rule["patterns"]:
                for alt in self._alternatives(pattern):
                    self._fuzzy_alts.append((rule, alt))
        self.stats = stats or ReflexStats()
        self._rng = rng or random.Random()  # noqa: S311  (jitter/replies, not crypto)

    @staticmethod
    def _alternatives(pattern: str) -> List[str]:
        """Expand a pattern's ``(a|b|c)`` alternations into plain phrases.

        Parameterized patterns (``(.+)``/``(.*)``) are skipped — fuzzy
        matching a free-text capture group is meaningless; the regex
        stage already handles those.
        """
        if "(.+)" in pattern or "(.*)" in pattern:
            return []
        # Iteratively expand the leftmost (a|b|...) group (no nesting in
        # this table — verified at extraction).
        expansions = [pattern]
        out: List[str] = []
        for _ in range(8):  # safety bound
            nxt: List[str] = []
            changed = False
            for exp in expansions:
                m = re.search(r"\(([^()]+)\)", exp)
                if not m:
                    out.append(exp)
                    continue
                changed = True
                for alt in m.group(1).split("|"):
                    nxt.append(exp[:m.start()] + alt + exp[m.end():])
            expansions = nxt
            if not changed:
                break
        cleaned = []
        for exp in out:
            exp = re.sub(r"[\^$\?]", "", exp).strip()
            exp = re.sub(r"\s+", " ", exp)
            if exp:
                cleaned.append(exp.lower())
        return cleaned

    def match(self, text: str) -> Optional[ReflexHit]:
        cleaned = normalize(text)
        if not cleaned:
            return None

        # Stage 1: regex (confidence 1.0).
        for rule, compiled in self._compiled:
            for rx in compiled:
                m = rx.search(cleaned)
                if m:
                    groups = [g or "" for g in m.groups()]
                    return ReflexHit(
                        rule_id=rule["id"], tool=rule["tool"],
                        args=dict(rule["args"]), reply=rule["reply"],
                        compute=rule["compute"], confidence=1.0,
                        groups=groups)

        # Stage 2: fuzzy over expanded alternatives
        # (confidence = score/100). Legacy parity: the dummy match's group
        # 1 is the whole utterance.
        try:
            from fuzzywuzzy import fuzz
        except ImportError:
            return None
        best_rule, best_score = None, 0
        for rule, alt in self._fuzzy_alts:
            score = fuzz.ratio(alt, cleaned)
            # Defensive: the fuzzy stage is best-effort. If the scorer was
            # stubbed/broken (e.g. a MagicMock in tests), skip it rather
            # than crashing the match.
            if not isinstance(score, (int, float)):
                continue
            if score > _FUZZY_THRESHOLD and score > best_score:
                best_score, best_rule = score, rule
        if best_rule is not None:
            return ReflexHit(
                rule_id=best_rule["id"], tool=best_rule["tool"],
                args=dict(best_rule["args"]), reply=best_rule["reply"],
                compute=best_rule["compute"],
                confidence=best_score / 100.0, groups=[cleaned])
        return None


# ---------------------------------------------------------------------------
# Stats (persisted coverage report for `jarvis reflex stats`)
# ---------------------------------------------------------------------------

def _default_stats_path() -> str:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        d = os.path.join(base, "jarvis")
    else:
        d = os.path.join(os.path.expanduser("~"), ".jarvis")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "reflex_stats.json")


class ReflexStats:
    """Persistent reflex-coverage counters (local only)."""

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path or _default_stats_path()
        self._lock = threading.Lock()
        self._data = {"total": 0, "reflex": 0, "rules": {},
                      "updated": None}
        self._load()

    def _load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self._data.update(data)
        except (OSError, ValueError):
            pass

    def _save(self) -> None:
        try:
            self._data["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f)
            os.replace(tmp, self.path)
        except OSError:
            logger.warning("could not persist reflex stats", exc_info=True)

    def record(self, rule_id: Optional[str]) -> None:
        """Record one utterance; rule_id=None means it went to the LLM."""
        with self._lock:
            self._data["total"] += 1
            if rule_id:
                self._data["reflex"] += 1
                rules = self._data.setdefault("rules", {})
                rules[rule_id] = rules.get(rule_id, 0) + 1
            self._save()

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            total = self._data["total"]
            reflex = self._data["reflex"]
            rules = dict(self._data.get("rules", {}))
        top = sorted(rules.items(), key=lambda kv: kv[1], reverse=True)[:10]
        return {"total": total, "reflex": reflex,
                "pct": (100.0 * reflex / total) if total else 0.0,
                "top_rules": top,
                "updated": self._data.get("updated")}


def print_stats() -> None:
    """`jarvis reflex stats` — how much traffic the reflex layer absorbs."""
    s = ReflexStats().summary()
    print("Reflex layer coverage")
    print(f"  utterances : {s['total']}")
    print(f"  via reflex : {s['reflex']} ({s['pct']:.1f}%)")
    print(f"  via LLM    : {s['total'] - s['reflex']}")
    if s["top_rules"]:
        print("  top rules  :")
        for rule_id, count in s["top_rules"]:
            print(f"    {rule_id}: {count}")
    if s["updated"]:
        print(f"  updated    : {s['updated']}")
    if not s["total"]:
        print("  (no utterances recorded yet — stats accumulate as you use JARVIS)")
