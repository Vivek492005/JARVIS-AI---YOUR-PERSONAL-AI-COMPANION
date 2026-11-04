"""Control center API (Master Plan Task 7.7).

JSON APIs behind the same bearer-token auth as the rest of jarvisd:
- settings: view (secrets redacted) + update (allowlisted fields only)
- audit: query + stats (the audit viewer for the HUD control page)
- memory: view / add / delete facts
- skills: list with permissions + enable/disable
- providers: latency/health snapshot
- costs: daily token/INR usage vs budgets (CostGuard)

Every route is read/write-safe by construction: PUT /api/settings only
touches an explicit allowlist, secrets are never returned or accepted here.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# --- settings -------------------------------------------------------------

# section.attr -> (coerce, validate)
def _int_range(lo: int, hi: int):
    def f(v):
        v = int(v)
        if not lo <= v <= hi:
            raise ValueError(f"must be {lo}..{hi}")
        return v
    return f


SETTABLE: Dict[str, Callable[[Any], Any]] = {
    "safety.autonomy_level": _int_range(0, 3),
    "voice.tts_engine": str,
    "voice.neural_voice": str,
    "voice.rumik_voice": str,
    "voice.voice_volume": lambda v: max(0.0, min(1.5, float(v))),
    "voice.tts_rate": lambda v: max(-10, min(10, int(v))),
    "voice.voice_custom_consent": lambda v: bool(v) if isinstance(v, bool) else v,
    "privacy.privacy_mode": bool,
    "privacy.allow_huggingface": bool,
    "privacy.allow_deepseek": bool,
    "privacy.allow_rumik_tts": bool,
    "privacy.allow_google_stt": bool,
    "brain.daily_token_budget": lambda v: max(0, int(v)),
    "brain.daily_cost_inr_budget": lambda v: max(0.0, float(v)),
}


def _redact_settings(settings) -> Dict[str, Any]:
    """model_dump with credential fields masked.

    Uses a narrower rule than audit.redact_value on purpose: budget fields
    like ``daily_token_budget`` must stay visible for the cost dashboard.
    Only real credential names (api_key/_secret/_token/password/…) and
    issued-token-looking values are masked.
    """
    import re
    from jarvis.policy.audit import _REDACT_VALUE_PATTERNS
    cred_re = re.compile(
        r"(api_key|_secret|_token|password|passwd|auth|credential|"
        r"private_key|access_key|bearer)$",
        re.IGNORECASE)
    out = {}
    for section in ("voice", "brain", "safety", "privacy"):
        part = settings.model_dump().get(section, {})
        clean = {}
        for k, v in part.items():
            secret = bool(cred_re.search(k or "")) and v
            if not secret and isinstance(v, str):
                secret = any(p.match(v.strip()) for p in _REDACT_VALUE_PATTERNS)
            clean[k] = "***REDACTED***" if secret else v
        out[section] = clean
    return out


# --- request models --------------------------------------------------------

class SettingsUpdate(BaseModel):
    updates: Dict[str, Any]


class FactCreate(BaseModel):
    key: str
    value: str
    # MemoryStore only accepts 'user' | 'confirmed' sources (Phase 4).
    source: str = "user"


# --- push notifications (Task 7.9) -----------------------------------------
# Web Push delivery needs the optional `pywebpush` package + VAPID keys
# (JARVIS_VAPID_PRIVATE_KEY / JARVIS_VAPID_PUBLIC_KEY env). Without them the
# endpoints still store subscriptions and notify_push() logs instead of
# sending — the in-page Notification API (app.js) covers the HUD-open case.

class PushSubscription(BaseModel):
    endpoint: str
    keys: Dict[str, str] = {}


class ProposalReject(BaseModel):
    reason: str = ""


class ProposalEdit(BaseModel):
    title: Optional[str] = None
    body: Optional[Dict[str, Any]] = None


def _learning_service(service):
    """Lazily attach a LearningService to the jarvisd service object.

    Tests may pre-attach a fake ``service.learning``; production gets the
    default (``~/.jarvis/learning.db``).
    """
    svc = getattr(service, "learning", None)
    if svc is None:
        from jarvis.learning.service import LearningService
        svc = LearningService.default()
        try:
            service.learning = svc
        except Exception:  # noqa: S110 - caching is best-effort only
            pass
    return svc


def _push_store_path() -> Path:
    from jarvis.core.config import get_settings
    try:
        base = Path(get_settings().brain.memory_workspace or "~/.jarvis")
    except Exception:
        base = Path("~/.jarvis")
    return base.expanduser() / "push_subscriptions.json"


def _load_subscriptions() -> List[Dict[str, Any]]:
    p = _push_store_path()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _save_subscriptions(subs: List[Dict[str, Any]]) -> None:
    p = _push_store_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(subs, indent=2), encoding="utf-8")


def notify_push(title: str, body: str) -> int:
    """Best-effort Web Push to all stored subscriptions.

    Returns the number of pushes accepted for delivery. 0 when pywebpush
    or the VAPID keys aren't configured (logged, not raised).
    """
    import os
    subs = _load_subscriptions()
    if not subs:
        return 0
    priv = os.environ.get("JARVIS_VAPID_PRIVATE_KEY", "")
    pub = os.environ.get("JARVIS_VAPID_PUBLIC_KEY", "")
    if not (priv and pub):
        logger.info("push: %d subscription(s) stored but no VAPID keys — "
                    "skipping (%s)", len(subs), title)
        return 0
    try:
        from pywebpush import webpush
    except ImportError:
        logger.info("push: pywebpush not installed — skipping (%s)", title)
        return 0
    sent = 0
    for sub in subs:
        try:
            webpush(subscription_info=sub,
                    data=json.dumps({"title": title, "body": body}),
                    vapid_private_key=priv,
                    vapid_claims={"sub": "mailto:jarvis@localhost"})
            sent += 1
        except Exception as e:  # WebPushException and friends
            logger.warning("push to %s failed: %s",
                           str(sub.get("endpoint", ""))[:60], e)
    return sent


# --- router factory --------------------------------------------------------

def build_control_router(service, verify) -> APIRouter:
    """Build the control-center router. `verify` is the auth dependency."""
    r = APIRouter(prefix="/api", dependencies=[Depends(verify)])

    @r.get("/settings")
    def get_settings():
        from jarvis.core.config import get_settings
        return _redact_settings(get_settings())

    @r.put("/settings")
    def put_settings(body: SettingsUpdate):
        from jarvis.core.config import get_settings, _write_settings_toml
        settings = get_settings()
        applied, rejected = [], []
        for dotted, raw in body.updates.items():
            coerce = SETTABLE.get(dotted)
            if coerce is None:
                rejected.append(dotted)
                continue
            section, attr = dotted.split(".", 1)
            target = getattr(settings, section, None)
            if target is None or not hasattr(target, attr):
                rejected.append(dotted)
                continue
            try:
                setattr(target, attr, coerce(raw))
                applied.append(dotted)
            except Exception as e:
                logger.warning("settings update %s failed: %s", dotted, e)
                rejected.append(dotted)
        try:
            _write_settings_toml(settings)
        except Exception as e:
            raise HTTPException(500, f"persist failed: {e}") from e
        return {"applied": applied, "rejected": rejected}

    @r.get("/audit")
    def audit_query(day: Optional[str] = None, tool: Optional[str] = None,
                    decision: Optional[str] = None, limit: int = 50):
        from jarvis.policy import audit
        return audit.query(day=day, tool=tool, decision=decision,
                           limit=min(limit, 500))

    @r.get("/audit/stats")
    def audit_stats(day: Optional[str] = None):
        from jarvis.policy import audit
        return audit.stats(day=day)

    @r.get("/memory/facts")
    def memory_facts():
        store = _memory_store(service)
        return [dict(id=f.id, key=f.key, value=f.value,
                     source=f.source, importance=f.importance)
                for f in store.all_facts()]

    @r.post("/memory/facts")
    def memory_add(body: FactCreate):
        store = _memory_store(service)
        store.add_fact(body.key, body.value, source=body.source)
        return {"ok": True}

    @r.delete("/memory/facts/{fact_id}")
    def memory_delete(fact_id: int):
        store = _memory_store(service)
        if not store.delete_fact(fact_id):
            raise HTTPException(404, "fact not found")
        return {"ok": True}

    @r.get("/skills")
    def skills_list():
        from jarvis.core.config import get_settings
        from jarvis.brain.skills import load_manifest
        try:
            d = Path(get_settings().brain.skills_dir)
        except Exception:
            d = Path("skills")
        out = []
        if d.exists():
            for child in sorted(d.iterdir()):
                if not (child / "SKILL.md").exists():
                    continue
                try:
                    m = load_manifest(child)
                    out.append({
                        "name": m.name,
                        "version": m.version,
                        "description": m.description,
                        "trust": m.trust.value if hasattr(m.trust, "value") else str(m.trust),
                        "tools": [{"name": t.name, "risk": str(t.risk)} for t in m.tools],
                        "permissions": list(m.permissions or []),
                        "enabled": not (child / ".disabled").exists(),
                    })
                except Exception as e:
                    out.append({"name": child.name, "error": str(e)})
        return out

    @r.post("/skills/{name}/enable")
    def skill_enable(name: str):
        _skill_flag(name, enable=True)
        return {"ok": True, "name": name, "enabled": True}

    @r.post("/skills/{name}/disable")
    def skill_disable(name: str):
        _skill_flag(name, enable=False)
        return {"ok": True, "name": name, "enabled": False}

    @r.get("/providers")
    def providers_status():
        """Latency/health snapshot. Degrades gracefully when the brain
        isn't attached (e.g. plain `serve --http` without full stack)."""
        out: Dict[str, Any] = {"providers": []}
        agent = getattr(service, "agent", None)
        router = getattr(agent, "model_router", None) if agent else None
        if router is None:
            return out
        for name in ("rumik", "huggingface", "deepseek", "local"):
            out["providers"].append({"name": name, "status": "unknown"})
        return out

    @r.get("/costs")
    def costs():
        agent = getattr(service, "agent", None)
        guard = getattr(agent, "cost_guard", None) if agent else None
        if guard is None:
            return {"today": None, "note": "cost tracking not attached"}
        tok_budget, inr_budget = guard._budgets()
        return {
            "date": guard._day,
            "prompt_tokens": guard.used.prompt_tokens,
            "completion_tokens": guard.used.completion_tokens,
            "cost_inr": round(guard.used.cost_inr, 2),
            "token_budget": tok_budget,
            "inr_budget": inr_budget,
            "breached": guard.breached,
        }

    @r.get("/push/vapid-key")
    def vapid_key():
        import os
        pub = os.environ.get("JARVIS_VAPID_PUBLIC_KEY", "")
        if not pub:
            raise HTTPException(404, "push not configured (no VAPID public key)")
        return {"public_key": pub}

    @r.post("/push/subscribe")
    def push_subscribe(body: PushSubscription):
        subs = _load_subscriptions()
        subs = [s for s in subs if s.get("endpoint") != body.endpoint]
        subs.append({"endpoint": body.endpoint, "keys": body.keys})
        _save_subscriptions(subs)
        return {"ok": True, "subscriptions": len(subs)}

    @r.delete("/push/subscribe")
    def push_unsubscribe(endpoint: str):
        subs = [s for s in _load_subscriptions()
                if s.get("endpoint") != endpoint]
        _save_subscriptions(subs)
        return {"ok": True, "subscriptions": len(subs)}

    # --- learning loop: proposals inbox (Phase 9 moonshot) ------------------
    # Every state-changing endpoint here is an explicit human decision,
    # audit-logged by the reviewer. Approval runs the eval gate first
    # (fail-closed) and may take a few minutes — the UI polls.

    @r.get("/learning/status")
    def learning_status():
        return _learning_service(service).status()

    @r.post("/learning/enable")
    def learning_enable():
        return _learning_service(service).set_enabled(True)

    @r.post("/learning/disable")
    def learning_disable():
        return _learning_service(service).set_enabled(False)

    @r.post("/learning/analyze")
    def learning_analyze(min_evidence: int = 3):
        svc = _learning_service(service)
        return {"new_proposals": svc.analyze(
            min_evidence=max(2, min(min_evidence, 50)))}

    @r.post("/learning/ingest-audit")
    def learning_ingest_audit(limit: int = 2000):
        svc = _learning_service(service)
        return svc.ingest_audit(limit=max(1, min(limit, 10000)))

    @r.get("/learning/proposals")
    def learning_proposals(status: str = ""):
        svc = _learning_service(service)
        return svc.reviewer.list(status=status)

    @r.get("/learning/proposals/{pid}")
    def learning_proposal(pid: str):
        svc = _learning_service(service)
        p = svc.reviewer.get(pid)
        if p is None:
            raise HTTPException(404, f"unknown proposal {pid}")
        return p

    @r.post("/learning/proposals/{pid}/approve")
    def learning_approve(pid: str):
        svc = _learning_service(service)
        out = svc.approve(pid, reviewer="control-center")
        if not out.ok:
            raise HTTPException(409, out.message)
        return {"ok": True, "proposal": out.proposal_id,
                "applied_id": out.applied_id, "message": out.message}

    @r.post("/learning/proposals/{pid}/reject")
    def learning_reject(pid: str, body: ProposalReject):
        svc = _learning_service(service)
        out = svc.reviewer.reject(pid, reason=body.reason,
                                  reviewer="control-center")
        if not out.ok:
            raise HTTPException(409, out.message)
        return {"ok": True, "message": out.message}

    @r.put("/learning/proposals/{pid}")
    def learning_edit(pid: str, body: ProposalEdit):
        svc = _learning_service(service)
        out = svc.reviewer.edit(pid, title=body.title, body=body.body,
                                reviewer="control-center")
        if not out.ok:
            raise HTTPException(409, out.message)
        return {"ok": True, "message": out.message}

    @r.get("/learning/applied")
    def learning_applied():
        svc = _learning_service(service)
        return svc.reviewer.store.list_applied()

    @r.post("/learning/applied/{aid}/revert")
    def learning_revert(aid: int):
        svc = _learning_service(service)
        out = svc.reviewer.revert(aid, reviewer="control-center")
        if not out.ok:
            raise HTTPException(409, out.message)
        return {"ok": True, "message": out.message}

    @r.get("/learning/runs")
    def learning_runs(limit: int = 50):
        svc = _learning_service(service)
        return svc.reviewer.store.recent_runs(
            limit=max(1, min(limit, 500)), learnable_only=False)

    return r


def _memory_store(service):
    from jarvis.brain.memory.store import MemoryStore
    store = getattr(service, "memory", None)
    if store is None:
        from jarvis.core.config import get_settings
        s = get_settings()
        ws = (getattr(getattr(s, "brain", None), "memory_workspace", None)
              or getattr(s, "memory_workspace", None) or "~/.jarvis")
        store = MemoryStore(Path(ws).expanduser() / "memory.db")
    return store


def _skill_flag(name: str, enable: bool) -> None:
    from jarvis.core.config import get_settings
    try:
        d = Path(get_settings().brain.skills_dir)
    except Exception:
        d = Path("skills")
    skill_dir = d / name
    if not (skill_dir / "SKILL.md").exists():
        raise HTTPException(404, f"skill {name!r} not found")
    flag = skill_dir / ".disabled"
    if enable:
        flag.unlink(missing_ok=True)
    else:
        flag.touch()
