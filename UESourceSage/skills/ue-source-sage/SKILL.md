---
name: ue-source-sage
description: Guide one main Agent through isolated Unreal Engine source-learning domains and Build.cs-scoped submodules using scoped role specifications. Use when creating or continuing a UE source study, mapping architecture, tracing runtime behavior, managing learning stages, caching questions, activating domain-specific or submodule-specific roles, validating routing, or enforcing an explicit Unreal source allowlist without mixing unrelated modules.
---

# UE Source Sage

Use one main Agent runtime. Activate one role specification at a time; roles specialize the same Agent runtime.

## Start Every Task

1. Run `python skills/ue-source-sage/scripts/sage.py preflight`. If it fails, stop; do not create, discover, confirm, read, or advance anything.
2. Read `<workspace>/config/global.yaml` and `modules/index.md`.
3. Resolve one learning-domain module. Create it only when the user explicitly starts that study.
4. Resolve one submodule from `<module>/submodules/index.md`. A submodule owns exactly one explicitly configured Build.cs file.
5. Read only the selected module/submodule manifests, routers, small process state, compact question indexes, and applicable role specifications.
6. Normalize intent, topic or symbol, depth, and engine version.
7. Route to the smallest indexes and at most the configured canonical-document budget.
8. Activate one effective role for the current task or process stage.
9. Access Unreal source only through `scripts/sage.py source read/search`; these commands enforce the selected submodule allowlist.
10. Activate an executable route before source access. The route records one domain, one submodule, intent, topic, role, index set, and canonical-document budget.

If the Build.cs path is unknown, run metadata-only discovery after preflight. Present the candidates and wait for explicit user confirmation before creating submodules. Discovery may inspect only paths, file names, `*.uplugin` names, and `*.Build.cs` names; it never reads implementation source and does not require a separate authorization step.

Read [module-contract.md](references/module-contract.md) before creating scopes, [routing-protocol.md](references/routing-protocol.md) before source analysis, and [role-protocol.md](references/role-protocol.md) before defining or activating a role.

For a new or ambiguous domain, follow [domain-initialization.md](references/domain-initialization.md) and use [initialization-prompts.md](references/initialization-prompts.md). Do not create submodules until Build.cs candidates are explicitly confirmed.

## Maintain State

Both domain modules and submodules own independent `process/` and `questions/` systems. Use the narrowest applicable scope: submodule by default, domain module only for cross-submodule learning state or questions.

Read [process-protocol.md](references/process-protocol.md) before stage transitions and [questions-protocol.md](references/questions-protocol.md) before question mutations. Use the CLI so canonical state, rendered views, and append-only history stay consistent.

## Use Deterministic Operations

```powershell
python skills/ue-source-sage/scripts/sage.py validate
python skills/ue-source-sage/scripts/sage.py preflight
python skills/ue-source-sage/scripts/sage.py module create <DomainName>
python skills/ue-source-sage/scripts/sage.py discover build-cs <query> --within <EngineRelativeRoot>
python skills/ue-source-sage/scripts/sage.py module confirm <domain-id> --build-cs <EngineRelativeBuildCs>
python skills/ue-source-sage/scripts/sage.py submodule create <domain-id> <Name> --build-cs <RelativeBuildCs>
python skills/ue-source-sage/scripts/sage.py source check <domain-id> <submodule-id> <EngineRelativePath>
python skills/ue-source-sage/scripts/sage.py process show <domain-id> --submodule <submodule-id>
python skills/ue-source-sage/scripts/sage.py question list <domain-id> --submodule <submodule-id>
python skills/ue-source-sage/scripts/sage.py knowledge create <domain-id> --submodule <submodule-id> --title "..." --answer "..." --source "path/to/source.h:10"
python skills/ue-source-sage/scripts/sage.py knowledge update <domain-id> <document-id> --submodule <submodule-id> --answer "..."
python skills/ue-source-sage/scripts/sage.py knowledge validate <domain-id> --submodule <submodule-id>
python skills/ue-source-sage/scripts/sage.py knowledge archive <domain-id> <document-id> --submodule <submodule-id> --reason "superseded"
python skills/ue-source-sage/scripts/sage.py question promote <domain-id> Q-0001 --from-submodule <submodule-id> --reason "spans submodules"
python skills/ue-source-sage/scripts/sage.py route activate <domain-id> <submodule-id> --intent explain --topic "..."
python skills/ue-source-sage/scripts/sage.py route show
python skills/ue-source-sage/scripts/sage.py version status <domain-id>
python skills/ue-source-sage/scripts/sage.py version migrate <domain-id> --reason "engine upgrade"
```

Use `--dry-run` or an isolated temporary workspace for demonstrations. Do not create a concrete learning domain merely to test the framework.
