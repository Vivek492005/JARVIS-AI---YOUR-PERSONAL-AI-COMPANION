# Case study: building JARVIS, a safety-first voice AI for Windows

## Problem

Voice assistants can set timers. "AI agents" can edit code. Nobody had
built a voice-driven agent that safely operates a *person's whole Windows
computer* — opening apps, managing files, acting on the desktop — without
becoming a prompt-injection disaster. The gap wasn't capability; it was
**trust**: one misunderstood command ("empty the recycle bin") or one
malicious email body and the assistant becomes the attacker.

## Architecture

JARVIS is a layered system with one non-negotiable rule: **every tool call
passes through a single policy gate** (`policy.decide()`), regardless of
which layer requested it — reflex rules, the LLM, the scheduler, Telegram,
or MCP.

- **Reflex layer** (152 locally-extracted rules): instant, no-LLM handling
  of common commands — including Hindi verb-final phrasing ("chrome kholo").
- **Model router**: tiered LLM chain (fast → strong → local) with cost
  guards and a semantic cache.
- **Tool registry**: every capability is a `ToolSpec` with a risk tier
  (READ < REVERSIBLE < DESTRUCTIVE < SYSTEM), arg schemas, and timeouts.
- **Perception**: UIA control surface, OCR with PII redaction, browser
  agent with SSRF deny-listing, workspace-scoped file tools (trash-only
  delete — no permanent-delete tool exists by design).
- **Voice**: wake word → VAD → STT → agent → policy → TTS, with barge-in
  and earcons.

## Safety design (the interesting part)

| Threat | Mitigation |
|---|---|
| Prompt injection via email/web content | Outputs wrapped in `<untrusted_data>`; context taint forces confirmation for above-READ tools |
| Destructive accidents | L0–L3 autonomy dial; SYSTEM tools always confirm; timer-triggered actions above READ become notifications, never silent execution |
| Voice cloning abuse | XTTS custom voices need explicit consent + JARVIS-owned voice file |
| Supply chain (skills/MCP) | Third-party skills sandboxed; MCP servers allowlisted, default-DESTRUCTIVE, poisoned descriptions sanitized |
| Silent data exfiltration | Privacy egress toggles; offline mode kills all cloud calls; audit log is local |

Two real vulnerabilities were found and fixed during development: a policy
bypass in the local-fallback path (A-01) and a shell-injection in app
launching (A-02).

## Evals & results

- **1,169+ automated tests**, including a 468-test security suite at 100%.
- **250-case eval suite** gating the agent loop — 100% baseline *on mocked
  providers* (explicitly not a live-LLM quality claim).
- **Core coverage ≥ 80% enforced** by CI gate (policy, lanes, memory,
  router measured ~93%).
- **34-case prompt-injection corpus** in the containment tests.
- Perf: CLI cold start ~0.3 s (target < 3 s); reflex match < 0.05 s.

## Honest status

Built over 9 phases (audit → safety → runtime → voice → brain →
perception → integrations → HUD → release engineering), tagged
`v0.2.0`–`v0.10.0`. As of writing, the code is complete and Linux-tested;
**v1.0.0 is reserved for the first release verified on real Windows
hardware** — we don't claim "production-ready" before that.

## Resume bullets (for the author)

- Designed and built a voice-first Windows AI agent (9 phases, ~1,200
  tests, 93% core coverage) with a single policy gate enforcing
  risk-tiered autonomy across LLM, reflex, scheduler, and remote channels.
- Found and fixed 2 security vulnerabilities (policy bypass, shell
  injection) during a structured audit; wrote a 468-test security suite.
- Shipped release engineering: PyInstaller + Inno Setup pipeline, portable
  builds, SHA256-verified auto-updates, and a hardware verification
  checklist for v1.0.0.
