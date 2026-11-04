"""Tests for Phase 4.6 (skills) and 4.8 (reflection)."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
sys.modules.setdefault("pyautogui", MagicMock(name="pyautogui"))

from jarvis.brain.reflection import Reflector, parse_lesson  # noqa: E402
from jarvis.brain.skills.loader import (  # noqa: E402
    _parse_frontmatter,
    _parse_tools,
    load_all,
    load_manifest,
)
from jarvis.brain.skills.scaffold import new_skill  # noqa: E402
from jarvis.brain.skills.trust import TrustLevel, TrustStore  # noqa: E402
from jarvis.tools.registry import REGISTRY, Risk, ToolSpec  # noqa: E402


def _demo_spec(name="demo_tool_tp", risk=Risk.REVERSIBLE):
    from pydantic import BaseModel

    class P(BaseModel):
        pass

    return ToolSpec(name=name, description="d", params=P, risk=risk, handler=lambda a: ("ok", None))


@pytest.fixture
def clean_registry():
    """Remove demo tools from the global REGISTRY after each test."""
    yield
    for name in ("demo_tool_tp", "demo_tool_local"):
        REGISTRY.pop(name, None)


def _skill_dir(tmp_path, name="demo", tools_block="- name: demo_tool\n  risk: reversible"):
    d = tmp_path / name
    d.mkdir()
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Demo skill\nversion: 0.1.0\n"
        f"tools:\n  {tools_block}\n---\n\n# Demo\n",
        encoding="utf-8",
    )
    (d / "tool.py").write_text(
        "from jarvis.tools.registry import ToolSpec, Risk\n"
        "SPEC = ToolSpec(name='demo_tool', description='demo', risk=Risk.REVERSIBLE,\n"
        "                handler=lambda a: ('ok', None))\n",
        encoding="utf-8",
    )
    return d


# ---------------------------------------------------------------------------
# Manifest parsing
# ---------------------------------------------------------------------------


def test_parse_frontmatter_multiline_tools(tmp_path):
    d = _skill_dir(tmp_path)
    fm = _parse_frontmatter((d / "SKILL.md").read_text(encoding="utf-8"))
    assert fm["name"] == "demo"
    decls = _parse_tools(fm["tools"])
    assert decls[0].name == "demo_tool" and decls[0].risk == "reversible"


def test_load_manifest_requires_frontmatter(tmp_path):
    d = tmp_path / "bad"
    d.mkdir()
    (d / "SKILL.md").write_text("# no frontmatter\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_manifest(d)


# ---------------------------------------------------------------------------
# Trust: third-party defaults to DESTRUCTIVE
# ---------------------------------------------------------------------------


def test_third_party_tool_forced_destructive(clean_registry):
    from jarvis.brain.skills.loader import _register, SkillManifest, SkillToolDecl

    manifest = SkillManifest(
        name="x",
        description="x",
        tools=[SkillToolDecl("demo_tool", "reversible")],
        trust=TrustLevel.THIRD_PARTY,
    )
    out = _register(manifest, _demo_spec())
    assert out.risk == Risk.DESTRUCTIVE


def test_local_skill_keeps_declared_tier(clean_registry):
    from jarvis.brain.skills.loader import _register, SkillManifest, SkillToolDecl

    manifest = SkillManifest(
        name="x",
        description="x",
        tools=[SkillToolDecl("demo_tool_local", "reversible")],
        trust=TrustLevel.LOCAL,
    )
    assert _register(manifest, _demo_spec("demo_tool_local")).risk == Risk.REVERSIBLE


def test_trust_store_pins_and_verifies(tmp_path):
    from jarvis.brain.skills.trust import sha256_of

    store = TrustStore()
    f = tmp_path / "tool.py"
    f.write_text("x = 1\n", encoding="utf-8")
    store.pin("s", sha256_of(f))
    assert store.check("s", sha256_of(f)) is True
    f.write_text("x = 2\n", encoding="utf-8")  # tampered
    assert store.check("s", sha256_of(f)) is False
    assert store.check("never-pinned", "abc") is True


# ---------------------------------------------------------------------------
# load_all: dogfood skills + .disabled
# ---------------------------------------------------------------------------


def test_load_all_dogfood_skills():
    skills_dir = Path(__file__).resolve().parent.parent.parent / "skills"
    if not skills_dir.is_dir():
        pytest.skip("skills/ not present")
    loaded = load_all(skills_dir, local_names=frozenset(p.name for p in skills_dir.iterdir()))
    assert len(loaded) >= 9
    assert all(isinstance(m.name, str) for m in loaded)


def test_disabled_skill_skipped(tmp_path):
    _skill_dir(tmp_path, name="off")
    (tmp_path / "off.disabled").touch()
    assert load_all(tmp_path) == []


# ---------------------------------------------------------------------------
# Scaffold
# ---------------------------------------------------------------------------


def test_new_skill_scaffold(tmp_path):
    p = new_skill(tmp_path, "my-skill", tool_name="my_tool")
    assert (p / "SKILL.md").exists() and (p / "tool.py").exists()
    m = load_manifest(p)
    assert m.name == "my-skill"


# ---------------------------------------------------------------------------
# Reflection (4.8)
# ---------------------------------------------------------------------------


def test_parse_lesson_hinglish():
    lesson = parse_lesson("seekha: powershell fail hua -> quotes escape karke dobara chalao")
    assert lesson is not None and "quotes" in lesson.what_to_do


def test_parse_lesson_ignores_plain_text():
    assert parse_lesson("aaj mausam achha hai") is None


def test_reflector_records_failure_episode(tmp_path):
    from jarvis.brain.memory.store import MemoryStore

    store = MemoryStore(tmp_path / "m.db")
    try:
        r = Reflector(store)
        r.record_failure(
            "open_application",
            "app nahi mila",
            lesson_text="seekha: app nahi mila -> pehle installed apps check karo",
        )
        eps = store.recent_episodes(limit=5)
        outcomes = {e["outcome"] for e in eps}
        assert "failed" in outcomes and "lesson" in outcomes
    finally:
        store.close()


def test_weekly_proposals_needs_approval(tmp_path):
    from jarvis.brain.memory.store import MemoryStore

    store = MemoryStore(tmp_path / "m.db")
    try:
        r = Reflector(store)
        r.record_failure(
            "x", "kuch fail hua", lesson_text="lesson: test fail -> test wali baat yaad rakho"
        )
        props = r.weekly_proposals()
        # Proposals are strings for the user to approve; the Reflector never
        # writes to MEMORY.md itself (approval gate lives in ProfileStore).
        assert len(props) >= 1 and props[0].startswith("Seekha gaya:")
    finally:
        store.close()
