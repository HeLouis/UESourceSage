# {{submodule_name}} Submodule Router

Active domain: `{{parent_module_id}}`. Active Build.cs scope: `{{submodule_id}}`.

1. Read `submodule.yaml`, `process/state.json`, and the compact question index.
2. Treat only configured Build.cs parent directories and explicit allowed files as readable Unreal source.
3. Route through the smallest local indexes and canonical documents.
4. Record out-of-scope dependencies as boundaries or cached questions; do not read their source.
5. Use `sage.py source read/search {{parent_module_id}} {{submodule_id}} ...` for engine-source access.
6. Require an active route matching `{{parent_module_id}}/{{submodule_id}}`; source commands reject missing or stale route state.
