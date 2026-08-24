# {{module_name}} Router

Keep `{{module_name}}` (`{{module_id}}`) as the learning domain. This file routes; it grants no Unreal source access.

1. Read `module.yaml`, `initialization/state.json`, `submodules/index.md`, and domain `process/state.json`.
2. If initialization is not `ready_for_learning`, continue the initialization protocol; do not access source.
3. Select exactly one Build.cs-scoped submodule before source analysis.
4. Route cross-submodule questions at domain level; route ordinary work to the selected submodule.
5. Never infer source permission from a Build.cs dependency.
6. Use guarded source commands under the selected submodule.
