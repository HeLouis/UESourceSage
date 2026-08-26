# Process Protocol

`process/` records shared, versionable knowledge maturity. Domain process covers cross-submodule scope and synthesis; submodule process covers the selected Build.cs allowlist and is the default working process. Optional personal progress never drives either process.

## Default Stages

| Stage | Purpose | Required exit conditions |
|---|---|---|
| `scope` | Confirm source boundary, engine version, neighboring modules, and learning goal. | Stage record with work completed, exit assessment, handoff, and evidence. |
| `map` | Map directories, Build.cs dependencies, public entry points, and core types. | Stage record with work completed, exit assessment, handoff, and evidence. |
| `model` | Explain concepts, ownership, lifetimes, invariants, and data relationships. | Stage record plus at least one focused canonical knowledge document. |
| `trace` | Verify at least one end-to-end call or data flow. | Stage record with an ordered evidence trail. |
| `verify` | Cross-check evidence with source, tests, repros, or debugger plans. | Stage record with verification evidence and an explicit assessment. |
| `synthesize` | Produce a coherent learning map and retain unresolved questions explicitly. | Stage record and at least one canonical knowledge document. |

## Transition Rules

- Lifecycle: `not_started -> in_progress -> completed`; a stage may temporarily be `blocked`.
- Start only the current stage. Complete stages sequentially unless the module workflow is explicitly customized.
- Advance only with non-empty `summary`, `work_completed`, `exit_assessment`, `next_stage_handoff`, and at least one evidence reference. The CLI records these fields in both `process/state.json` and the stage artifact.
- Every stage must declare its machine-checkable deliverables: `scope` requires `source_boundary`, `engine_version`, and `learning_goal`; `map` requires `directories`, `dependencies`, and `entry_points`; `model` requires `concepts`, `ownership_lifetime`, `invariants`, and `canonical_document`; `trace` requires `ordered_flow`, `entry_point`, and `terminal_effect`; `verify` requires `verification_method` and `evidence_cross_check`; `synthesize` requires `canonical_map`, `question_disposition`, and `next_route`.
- `model` and `synthesize` cannot exit until the active scope has at least one document under `references/knowledge/`.
- `verify` additionally requires a canonical document marked `verified_source` or `experiment_verified`.
- Append every mutation to `history.jsonl`; never rewrite prior history.
- A stage artifact contains objectives, work completed, evidence, cached questions, exit assessment, and next-stage handoff.
- Reopening a completed stage requires an explicit reason and should not erase its prior completion event.

Read both small state files at task start, but mutate the narrowest applicable scope. Open only the active scope's current-stage artifact.
