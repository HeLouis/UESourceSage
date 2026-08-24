schema_version: 1

module:
  id: "{{module_id}}"
  name: "{{module_name}}"
  kind: "learning_domain"
  status: "active"
  created_at: "{{created_at}}"

engine:
  version: "{{engine_version}}"

routing:
  require_submodule_for_source_access: true
  max_canonical_docs: {{max_canonical_docs}}
