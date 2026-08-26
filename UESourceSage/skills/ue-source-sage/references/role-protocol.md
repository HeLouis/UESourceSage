# Role Protocol

UE Source Sage has one runtime: the main learning Agent. Roles are scoped instruction sets that the main Agent activates for a bounded task or process stage.

## Role Locations

- Global reusable roles: `skills/ue-source-sage/roles/`.
- Learning-domain roles: `modules/<domain-id>/roles/`.
- Build.cs submodule roles: `modules/<domain-id>/submodules/<submodule-id>/roles/`.

The Skill package may contain `skill-ui.yaml` for UI metadata. It is packaging metadata, not a runtime role.

## Role Resolution

Resolve rules from broad to narrow:

```text
global role
  + domain role
  + submodule role
  = effective role specification for the main Agent
```

Global rules define hard boundaries for source access, evidence, process, questions, and output safety. Domain and submodule roles may specialize or tighten those rules; they may never loosen them.

## Role Contract

Every role file should state:

- role name and purpose;
- applicable process stage and intent;
- required inputs;
- permitted context and source scope;
- required work;
- required artifact or output shape;
- evidence requirements;
- prohibited behavior;
- handoff information for the next role.

## Activation

At any point, the main Agent activates one effective role specification. During a learning session it may switch roles as the process stage or intent changes, while retaining the same runtime identity, scope, and evidence ledger.

Typical sequence:

```text
scope-mapper → source-mapper → mechanism-analyst → callflow-tracer → evidence-checker → question-curator
```

This is role switching by one Agent within one context and one evidence ledger.
