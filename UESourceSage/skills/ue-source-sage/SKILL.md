---
name: ue-source-sage
description: Route, study, and maintain isolated Unreal Engine source-learning domains and Build.cs-scoped submodules. Use when creating or continuing a UE source study, mapping architecture, tracing runtime behavior, managing module or submodule learning stages, caching valuable questions, assigning specialized agents, validating routing, or enforcing an explicit Unreal source allowlist without mixing unrelated modules.
---

# UE Source Sage

Keep one learning-domain module and one Build.cs-scoped submodule active. A Build.cs dependency is boundary evidence, never source-access authorization.

## Start Every Task

1. Read `<workspace>/config/global.yaml` and `modules/index.md`.
2. Resolve one learning-domain module. Create only its empty framework when the user explicitly starts that study.
3. Resolve one submodule from `<module>/submodules/index.md`. A submodule owns exactly one explicitly configured Build.cs file.
4. Read only the selected module/submodule manifests, routers, small process state, and compact question indexes.
5. Normalize intent, topic or symbol, depth, and engine version.
6. Route to the smallest indexes and at most the configured canonical-document budget.
7. Access Unreal source only through `scripts/sage.py source read/search`; these commands enforce the selected submodule allowlist.

If the Build.cs path is unknown, request it or explicit discovery authorization. Do not inspect the engine tree before a submodule allowlist exists.

Read [module-contract.md](references/module-contract.md) before creating scopes, [routing-protocol.md](references/routing-protocol.md) before source analysis, and [agent-protocol.md](references/agent-protocol.md) before selecting or creating a specialized agent.

## Maintain State

Both domain modules and submodules own independent `process/` and `questions/` systems. Use the narrowest applicable scope: submodule by default, domain module only for cross-submodule learning state or questions.

Read [process-protocol.md](references/process-protocol.md) before stage transitions and [questions-protocol.md](references/questions-protocol.md) before question mutations. Use the CLI so canonical state, rendered views, and append-only history stay consistent.

## Use Deterministic Operations

Run from the workspace root:

```powershell
python skills/ue-source-sage/scripts/sage.py validate
python skills/ue-source-sage/scripts/sage.py module create <DomainName>
python skills/ue-source-sage/scripts/sage.py submodule create <domain-id> <Name> --build-cs <RelativeBuildCs>
python skills/ue-source-sage/scripts/sage.py source check <domain-id> <submodule-id> <EngineRelativePath>
python skills/ue-source-sage/scripts/sage.py process show <domain-id> --submodule <submodule-id>
python skills/ue-source-sage/scripts/sage.py question list <domain-id> --submodule <submodule-id>
```

Use `--dry-run` or an isolated temporary workspace for demonstrations. Do not create a concrete learning domain merely to test the framework.
