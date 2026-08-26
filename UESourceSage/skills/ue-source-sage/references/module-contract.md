# Module And Submodule Contract

## Two Levels

- A **domain module** is the user-facing learning domain, such as a plugin family or architectural topic. It does not grant Unreal source access.
- A **submodule** is the smallest active learning scope. It contains exactly one explicitly configured `*.Build.cs` and grants access only to that Build.cs parent directory plus explicitly allowed files.

```text
modules/<domain-id>/
├─ module.yaml
├─ ROUTER.md
├─ roles/
├─ initialization/
│  ├─ state.json
│  └─ history.jsonl
├─ submodules/
│  ├─ index.md
│  └─ <submodule-id>/
│     ├─ submodule.yaml
│     ├─ ROUTER.md
│     ├─ roles/
│     ├─ references/{indexes,sources,knowledge}/
│     ├─ process/
│     ├─ questions/
│     │  └─ history.jsonl
│     └─ validation/routing-scenarios.md
├─ references/{indexes,sources,knowledge}/
├─ process/
├─ questions/
│  └─ history.jsonl
└─ validation/routing-scenarios.md
```

The domain-level references store only cross-submodule architecture. Put ordinary conclusions, process events, and questions in the selected submodule.

## Source Allowlist

Store one Build.cs string in `submodule.yaml`. Derive one recursive source root from its parent directory. Store exceptional descriptor files, such as a `.uplugin`, under `scope.allowed_files`.

Apply these rules:

1. Deny by default.
2. Permit the configured Build.cs and files recursively below its parent directory.
3. Permit individually listed `allowed_files`.
4. Reject paths outside `engine.source_root`, including traversal and symlink escapes.
5. Never grant access because a Build.cs mentions a dependency.
6. Record a dependency outside the allowlist in `boundaries.index.md` or questions. To study it, activate or create the separate one-Build.cs submodule that owns it.
7. Access engine source through the guarded `source` CLI commands. Direct recursive reads of the engine tree violate the contract.

When a Build.cs path is unknown, metadata-only discovery may scan the configured `engine.source_root` (optionally narrowed with a relative `--within` root). This scan reads only paths and descriptor/file names, so it does not require separate authorization and does not create scopes. A domain may exist with zero submodules while waiting for the user's Build.cs confirmation.

## Validation

`validation/` contains route and boundary regression scenarios. It verifies that prompts select the intended submodule, read the smallest indexes, and reject out-of-scope source. It is framework quality assurance, not learned knowledge and not proof that a source conclusion is correct.

## Canonical Knowledge Documents

Keep one focused mechanism or question per document under `references/knowledge/`. Create it with `sage.py knowledge create`; the CLI maintains `references/indexes/sources.index.md`. Include scope and version, a quick answer, ordered source trail, mechanism, boundaries and misconceptions, and linked question IDs. Prefer file/symbol/line evidence over pasted source. Mark evidence as `draft`, `verified_source`, `inferred`, `experiment_verified`, or `stale_version`.

The configured engine version is part of every scope manifest. If it differs from the current global configuration, learning commands stop with an engine-version mismatch until the scope is reinitialized or its metadata is deliberately updated.

Use `version status` to inspect mismatches and `version migrate` with an explicit reason to update scope manifests. Migration marks affected knowledge documents `stale_version`, clears the active route, and records the event in process history; it never silently rewrites knowledge claims.
