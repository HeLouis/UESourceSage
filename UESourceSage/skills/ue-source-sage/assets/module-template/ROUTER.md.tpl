# {{module_name}} Router

Keep `{{module_name}}` (`{{module_id}}`) as the learning domain. This file routes; it grants no Unreal source access.

1. Read `module.yaml`, `submodules/index.md`, and domain `process/state.json`.
2. Select exactly one Build.cs-scoped submodule before source analysis.
3. Route cross-submodule questions at domain level; route ordinary work to the selected submodule.
4. Never infer source permission from a Build.cs dependency.
5. Use guarded source commands under the selected submodule.
