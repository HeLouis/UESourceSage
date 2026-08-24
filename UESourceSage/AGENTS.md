# UE Source Sage Workspace Protocol

Use the repository skill at `skills/ue-source-sage/SKILL.md` for every Unreal Engine source-learning task.

## Scope Model

- `modules/<domain-id>/` is a learning domain. It organizes related Unreal C++ modules but grants no engine-source access.
- `modules/<domain-id>/submodules/<submodule-id>/` is one learning submodule.
- One submodule must map to exactly one `*.Build.cs`. Never combine Build.cs files in a submodule.
- Keep exactly one domain and one submodule active during engine-source analysis.

## Start And Route

1. Read `config/global.yaml` and `modules/index.md`.
2. Run `python skills/ue-source-sage/scripts/sage.py preflight`; if it fails, stop all learning workflow actions.
3. Create a domain only when the user explicitly starts or initializes that learning domain.
4. Resolve its submodule with `submodules/index.md`.
5. If the unique Build.cs path is unknown, request it or explicit discovery authorization. Do not inspect the engine tree to guess it.
6. Read only the active manifests, routers, small process states, compact question indexes, and the smallest routed knowledge documents.

## Source Boundary

- Derive the only recursive source root from the active submodule's single Build.cs parent directory.
- Permit extra descriptor files only when explicitly listed in `allowed_files`.
- A dependency named inside Build.cs is boundary evidence, never access permission.
- Use guarded `source check/read/search` commands for engine source. Reject every path outside the active submodule allowlist.
- Treat engine source as read-only unless the user explicitly requests a source change.

## State And Agents

- Domain `process/` and `questions/` are only for cross-submodule scope, synthesis, and questions.
- Submodule `process/` and `questions/` are the default for ordinary learning work.
- Reusable roles live in `skills/ue-source-sage/agents/roles/`; domain roles live in `modules/<domain>/agents/`; submodule roles live in its `agents/`.
- Agent roles never grant source access. Start actual subagents only when the user explicitly requests delegation or parallel work.
- `validation/` stores routing and boundary regression scenarios; it is not learned knowledge or source evidence.
- For ambiguous domain names, use metadata-only discovery inside an explicitly authorized relative root, then ask the user to confirm candidates before creating submodules.
