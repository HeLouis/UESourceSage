# Process Protocol

`process/` records shared, versionable knowledge maturity. Domain process covers cross-submodule scope and synthesis; submodule process covers the selected Build.cs allowlist and is the default working process. Optional personal progress never drives either process.

## Default Stages

| Stage | Purpose | Required exit artifact |
|---|---|---|
| `scope` | Confirm source boundary, engine version, neighboring modules, and learning goal. | `stages/01-scope.md` |
| `map` | Map directories, Build.cs dependencies, public entry points, and core types. | `stages/02-map.md` |
| `model` | Explain concepts, ownership, lifetimes, invariants, and data relationships. | `stages/03-model.md` |
| `trace` | Verify at least one end-to-end call or data flow. | `stages/04-trace.md` |
| `verify` | Cross-check evidence with source, tests, repros, or debugger plans. | `stages/05-verify.md` |
| `synthesize` | Produce a coherent learning map and explicitly retain unresolved questions. | `stages/06-synthesize.md` |

## Transition Rules

- Lifecycle: `not_started -> in_progress -> completed`; a stage may temporarily be `blocked`.
- Start only the current stage. Complete stages sequentially unless the module workflow is explicitly customized.
- Advance only with a non-empty summary and at least one evidence reference.
- Append every mutation to `history.jsonl`; never rewrite prior history.
- A stage artifact contains objectives, work completed, evidence, cached questions, exit assessment, and next-stage handoff.
- Reopening a completed stage requires an explicit reason and should not erase its prior completion event.

Read both small state files at task start, but mutate the narrowest applicable scope. Open only the active scope's current-stage artifact.
