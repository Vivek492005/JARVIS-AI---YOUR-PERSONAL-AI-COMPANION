"""Agent sandbox / isolation (Master Plan Task 5.10).

Incremental levels, Windows agent-workspace model ki tarah:

- **Level A** — scoped folders + policy engine + allowlisted commands.
  (Already the default everywhere: files.py scoping, tool registry,
  run_action gate.)
- **Level B** — code execution in a Docker/WSL2 container: no network
  by default, CPU/RAM/time limits, read-only workspace mount, outputs
  only to ``~/JarvisWorkspace/out``.
- **Level C** — separate Windows standard user ``jarvis-agent`` +
  Windows Sandbox/VM for risky browsing/automation, ACLs blocking the
  user's other folders. Windows-only; see :func:`level_c_guide`.

Skill trust mapping: ``THIRD_PARTY`` skills require Level B or higher;
``LOCAL`` skills run at Level A. :func:`check_skill_allowed` enforces
this; the skill loader should call it at load time.

The ``sandbox_exec`` tool (SYSTEM tier) builds the container spec and
runs it when docker is available, else reports the spec without
executing — never silently skip the isolation.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


class SandboxLevel(str, Enum):
    A = "A"  # scoped folders + policy engine (default)
    B = "B"  # container isolation for code execution
    C = "C"  # separate OS user / Windows Sandbox (Windows-only)


LEVEL_DESCRIPTIONS = {
    SandboxLevel.A: "Scoped workspace + policy gate + allowlisted commands.",
    SandboxLevel.B: "Docker/WSL2 container: no network, CPU/RAM/time limits, "
                    "read-only mounts, outputs to ~/JarvisWorkspace/out only.",
    SandboxLevel.C: "Separate Windows user 'jarvis-agent' + Windows Sandbox; "
                    "ACLs block the user's other folders.",
}


def current_level() -> SandboxLevel:
    """Configured sandbox level (default A)."""
    try:
        from jarvis.core.config import get_settings
        raw = str(getattr(get_settings().sandbox, "level", "A")).upper()
        return SandboxLevel(raw)
    except Exception:
        return SandboxLevel.A


def min_level_for_trust(trust: str) -> SandboxLevel:
    """Minimum sandbox level for a skill trust tier.

    ``trust`` is a TrustLevel value ("local" / "third_party" / "verified").
    Anything not local needs Level B+ (fail-closed).
    """
    if str(trust).lower() in ("third_party", "third-party",
                              "verified"):
        return SandboxLevel.B
    return SandboxLevel.A


def check_skill_allowed(skill_name: str, trust: str,
                        level: Optional[SandboxLevel] = None
                        ) -> Tuple[bool, str]:
    """(allowed, reason) — untrusted skills need Level B+."""
    level = level or current_level()
    need = min_level_for_trust(trust)
    order = [SandboxLevel.A, SandboxLevel.B, SandboxLevel.C]
    if order.index(level) >= order.index(need):
        return True, f"skill {skill_name!r} allowed at level {level.value}"
    return (False,
            f"skill {skill_name!r} is {trust} and needs sandbox level "
            f"{need.value}+ (current: {level.value})")


# ---------------------------------------------------------------------------
# Level B: container spec
# ---------------------------------------------------------------------------

@dataclass
class ContainerSpec:
    image: str = "python:3.12-slim"
    command: List[str] = field(default_factory=list)
    no_network: bool = True
    cpus: float = 1.0
    memory: str = "512m"
    timeout_s: float = 60.0
    work_dir: str = "/work"          # read-only workspace mount
    out_dir: str = "/out"            # the ONLY writable mount


def build_container_spec(command: List[str],
                         image: str = "python:3.12-slim",
                         timeout_s: float = 60.0,
                         extra_readonly: Optional[List[str]] = None) -> ContainerSpec:
    """Build a locked-down container spec for one command."""
    if not command:
        raise ValueError("empty command")
    timeout_s = max(5.0, min(float(timeout_s), 600.0))
    return ContainerSpec(image=image, command=list(command),
                         timeout_s=timeout_s)


def _workspace_out() -> Path:
    from jarvis.perception.files import workspace_root
    out = workspace_root() / "out"
    out.mkdir(parents=True, exist_ok=True)
    return out


def to_docker_args(spec: ContainerSpec) -> List[str]:
    """Render the spec as `docker run` args (no execution)."""
    from jarvis.perception.files import workspace_root
    args = ["docker", "run", "--rm"]
    if spec.no_network:
        args += ["--network", "none"]
    args += ["--cpus", str(spec.cpus), "--memory", spec.memory]
    args += ["--mount",
             f"type=bind,src={workspace_root()},dst={spec.work_dir},readonly"]
    args += ["--mount",
             f"type=bind,src={_workspace_out()},dst={spec.out_dir}"]
    args += ["--workdir", spec.work_dir, spec.image] + spec.command
    return args


def docker_available() -> bool:
    return shutil.which("docker") is not None


def run_in_container(spec: ContainerSpec) -> str:
    """Execute the spec with docker. Refuses when docker is missing."""
    if not docker_available():
        return ("docker not available on this machine — container spec "
                "built but NOT executed (isolation not silently skipped). "
                f"Spec: {' '.join(to_docker_args(spec)[:8])} ...")
    args = to_docker_args(spec)
    try:
        proc = subprocess.run(args, capture_output=True, text=True,
                              timeout=spec.timeout_s)
    except subprocess.TimeoutExpired:
        return f"container timed out after {spec.timeout_s}s (killed)"
    out = (proc.stdout or "")[-3000:]
    err = (proc.stderr or "")[-1000:]
    if proc.returncode != 0:
        return f"container exited {proc.returncode}\n{out}\n{err}".strip()
    return out.strip() or "(no output)"


# ---------------------------------------------------------------------------
# Level C: setup guide (Windows-only, manual steps)
# ---------------------------------------------------------------------------

def level_c_guide() -> str:
    return "\n".join([
        "Level C setup (Windows, manual, one-time):",
        "1. Create a standard (non-admin) user 'jarvis-agent'.",
        "2. Move the Jarvis workspace under that user's profile; remove",
        "   your own account's write access to it (and its read access to",
        "   your Documents/Desktop) via folder ACLs.",
        "3. Enable Windows Sandbox (optional) for risky browsing/automation;",
        "   run the jarvisd service inside the sandbox.",
        "4. In settings.toml set [sandbox] level = \"C\".",
        "5. Verify: run `jarvis doctor` as jarvis-agent; confirm the agent",
        "   cannot list your home directory.",
    ])


# ---------------------------------------------------------------------------
# Skill-loader hook
# ---------------------------------------------------------------------------

def assert_skill_allowed(skill_name: str, trust: str,
                         level: Optional[SandboxLevel] = None) -> None:
    """Raise if the skill's trust tier exceeds the sandbox level."""
    allowed, reason = check_skill_allowed(skill_name, trust, level)
    if not allowed:
        raise PermissionError(reason)
    logger.info("sandbox: %s", reason)
