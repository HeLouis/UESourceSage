# Questions Protocol

Questions are durable knowledge debt, not a scratchpad. Cache a question in the active submodule by default. Use the domain queue only when the question genuinely spans multiple configured submodules.

## Lifecycle

| Status | Meaning |
|---|---|
| `open` | Worth retaining; investigation has not started. |
| `investigating` | An active source trail or experiment exists. |
| `answered` | A provisional answer and evidence are recorded. |
| `verified` | The answer is confirmed for the configured engine version. |
| `archived` | No longer relevant, duplicated, or superseded; retain the reason. |

## Required Fields

Every question has an id, exact question, why it is worth caching, topic, priority, discovery stage, status, timestamps, answer, and evidence list. The script derives the discovery stage from `process/state.json` unless explicitly supplied.

## Mutation Rules

1. Search `questions/index.md` before adding; prefer updating an existing question over paraphrased duplicates.
2. Keep the question narrow enough to be answered by a bounded source trail.
3. Do not move to `answered` without an answer and evidence.
4. Do not move to `verified` without version-appropriate source or experiment evidence.
5. Link stable answers into a canonical knowledge document; the question remains as provenance.
6. Record follow-up questions separately when they change the scope.

Each scope owns its own ids and canonical `questions/state.json`. Its `index.md` and `items/Q-xxxx.md` are rendered views. Mutate the intended scope with `scripts/sage.py question ... [--submodule <id>]`.
