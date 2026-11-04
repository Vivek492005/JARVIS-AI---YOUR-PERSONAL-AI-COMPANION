# Self-Improving Skills (Phase 9 Moonshot)

A Hermes-style learning loop for JARVIS skills — **human-reviewed, never
auto-applied**. The loop watches how skills are used, turns repeated
patterns into concrete improvement proposals, and a human approves (or
rejects) each one in the control center. Approval runs an eval gate first;
any regression blocks the change (fail-closed).

## The loop

```
  skill executions ──► LearningStore ──► proposer ──► proposals (pending)
        │                    ▲                  │
        │              audit ingest        human review
        │              undo hook           (control center / CLI)
        ▼                    │                  ▼
  corrections ───────────────┘            eval gate ──► apply (versioned,
                                                          reversible)
```

1. **Collect** (`learning/recorder.py`): skill executions (tool, redacted
   args, policy decision, latency) and corrections (undo events via a
   guarded hook in `UndoJournal.undo_last`, explicit corrections).
   Batch path: `jarvis learn ingest-audit` replays the redacted audit log.
2. **Propose** (`learning/proposer.py`, offline): clusters of repeated
   identical tool calls → `reflex_rule`; repeated corrections on a tool →
   `prompt_snippet`; frequent A→B tool sequences → `skill_variant`.
3. **Review** (control center → Learning card, or `jarvis learn`): the
   reviewer sees evidence, a diff/preview, and confidence. Approve runs
   the eval gate; reject/edit are one click.
4. **Apply** (`learning/reviewer.py`): versioned (backup stored), reversible
   (`revert` restores), audit-logged.

## Safety model

* **No auto-apply, ever.** The only path to a production change is an
  explicit human approval behind the control center's bearer-token auth.
* **Poisoning guard.** Rows carry `source_trust`; anything from `mcp`,
  `web`, `clipboard`, or `untrusted` sources is stored with
  `learnable=0` and can never feed a proposal. Tool outputs are treated as
  untrusted data (same stance as the Phase 4 memory poisoning guard).
* **Privacy.** Args are stored redacted (same redaction as the audit log);
  sensitive content is withheld entirely (hash only, for counting). Raw
  user utterances are never stored — learned reflex patterns are left blank
  for the reviewer to fill from utterances *they* observed.
* **Learned reflex rules are capability-capped.** A learned rule may only
  target READ/REVERSIBLE tools. A learned regex can never cause a
  DESTRUCTIVE/SYSTEM tool to fire without confirmation — the approval-time
  validator enforces this, and the matcher skips malformed entries.
* **Eval gate (fail-closed).** Approval re-runs eval subsets relevant to
  the change type, always including `safety` + `injection` at 100%.
  Timeout, parse failure, or any regression → the proposal stays pending.
* **Reversible.** Every apply stores a backup; `revert` restores it.
  Skill-variant scaffolds are inert (comment-only `tool.py`) until a
  developer implements them.
* **Kill switch.** `jarvis learn disable` (or the control-center toggle)
  stops all collection immediately. Re-enabling never backfills silently —
  use `ingest-audit` explicitly.

## Proposal types

| Type | Trigger | Applies to |
|---|---|---|
| `reflex_rule` | same tool+args executed N+ times | `src/jarvis/brain/reflex_learned.json` (merged after built-ins; built-ins win ties) |
| `prompt_snippet` | repeated corrections on a tool | `src/jarvis/brain/prompts/learned.md` (optional layer in the system prompt) |
| `skill_variant` | frequent A→B tool sequences | new `skills/<name>/` scaffold via `scaffold.new_skill` |

## Reviewer guide

1. Open Control Center → **Learning loop** (or `jarvis learn proposals`).
2. For each pending proposal: read the evidence (counts, not raw text),
   open **Detail** for the full payload.
3. `reflex_rule`: **fill in the regex patterns first** — the proposer
   cannot (it never saw the utterance). Test the pattern mentally against
   false positives; keep it tight (`^...$` anchored).
4. `prompt_snippet`: edit the draft so it reads like a rule you'd give a
   careful assistant, not a complaint.
5. `skill_variant`: the scaffold is a starting point — approve to create
   it, then implement `tool.py` yourself.
6. **Approve** → the eval gate runs (a few minutes). If it fails, the
   proposal stays pending with the report attached — inspect, edit, retry.
7. **Revert** any applied change from the Applied list if behaviour
   degrades in real use.

## What still needs a human

* Real review sessions on real usage (this VM has no live user traffic;
  the store starts empty).
* Filling reflex patterns (by design — see Privacy above).
* Implementing scaffolded skill variants.
* The `path` (reflex-vs-LLM) signal is recorded when the caller passes it;
  wiring it through the router is future work — current reflex proposals
  trigger on repetition alone, honestly labelled in their evidence.
