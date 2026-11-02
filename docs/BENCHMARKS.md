# Benchmarks — Task 8.7

> **Every number here is measured or marked TBD.** Nothing is estimated,
> extrapolated, or "typical". TBD rows get filled during the v1.0.0
> real-hardware run.

## Test suite (measured 2026-11-02, Linux VM, `v0.9.0` + Phase 8)

| Metric | Value |
|---|---|
| Unit + integration tests passing | 1169+ (grows with Phase 8) |
| Known pre-existing failures | 7 (5× provider ModuleNotFound, 1× observability, 1× privacy) |
| Core coverage (policy/lanes/memory/router) | ≥ 80% enforced, measured ~93% |
| Security suite | 468 tests, 100% pass (Phase 1) |

## Eval suite (measured, Phase 4)

| Metric | Value |
|---|---|
| Eval cases | 250 |
| Baseline gate | 100% pass **on fakes** |

!!! warning "Read this before quoting the eval number"
    The 100% baseline ran against **mocked** providers and tools. It proves
    the agent loop, policy wiring, and tool schemas are coherent — it is
    **not** a live-LLM quality claim. Live-LLM evals need API keys and are
    TBD.

## Latency (measured where possible)

| Metric | Target | Measured | Notes |
|---|---|---|---|
| CLI cold start | < 3 s | ~0.3 s | Linux VM |
| Reflex match (in-process) | < 0.5 s | < 0.05 s | Linux VM |
| p50 voice latency | ≤ 1.5 s | TBD | needs mic + provider on hardware |
| STT accuracy (Hinglish) | — | TBD | needs bake-off recordings |

## What we don't claim

- No "faster than X" without a measured A/B.
- No user counts, no stars, no installs — until they're real.
- No "production-ready" until the hardware checklist is green.
