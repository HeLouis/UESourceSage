schema_version: 1

submodule:
  id: "{{submodule_id}}"
  name: "{{submodule_name}}"
  parent_module: "{{parent_module_id}}"
  kind: "build_cs_scope"
  status: "active"
  created_at: "{{created_at}}"

engine:
  version: "{{engine_version}}"

scope:
  access_policy: "allowlist_only"
  source_root_from_build_cs: true
  build_cs: "{{build_cs}}"
  allowed_files:{{allowed_files_block}}

routing:
  max_canonical_docs: {{max_canonical_docs}}
  dependency_grants_access: false
