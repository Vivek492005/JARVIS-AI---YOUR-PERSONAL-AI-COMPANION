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
    cred_re = re.compile(r"(api_key|_secret|_token|password|passwd|auth|credential|private_key|access_key|bearer)$",
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
            raise HTTPException(500, f"persist failed: {e}")
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
