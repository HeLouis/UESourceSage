# Domain Initialization Protocol

Domain initialization turns a natural-language learning request into a confirmed learning domain and a set of one-Build.cs submodules. It does not begin mechanism analysis.

## State Machine

```text
requested
  → global_preflight_passed
  → domain_created
  → awaiting_build_scope
  → candidate_confirmation_required
  → submodules_registered
  → ready_for_learning
```

`blocked` may replace any active state when configuration or user input is missing. Every transition is appended to `initialization/history.jsonl` and reflected in `initialization/state.json`.

## Rules

1. Resolve the learning-domain name and intent before touching the engine tree.
2. Create the domain empty framework without reading engine source.
3. If `engine.source_root` is missing or invalid, fail global preflight before creating a domain or touching the engine tree.
4. If the Build.cs path is known, accept one explicit path at a time and verify only its existence and suffix.
5. If the name is ambiguous, run metadata-only discovery under `engine.source_root` (or an optional narrower relative root). Discovery may inspect only paths, file names, `*.uplugin` names, and `*.Build.cs` names; it must not read `.h`/`.cpp` implementations or create submodules. No separate discovery authorization is required.
6. Present candidates and wait for explicit confirmation. Never create every discovered candidate automatically.
7. Create exactly one submodule for each confirmed Build.cs. Reject duplicate Build.cs paths and any attempt to combine them.
8. Initialize the domain process at `scope`; initialize each new submodule process at `not_started`. Do not claim that source learning has begun until a submodule is selected.

## Metadata-only Discovery Boundary

Discovery is a temporary metadata-only scan, separate from active submodule source access:

```text
engine.source_root/<optional-within-root>/**
  allowed: path/name matching for *.Build.cs and *.uplugin
  denied: implementation content and all knowledge conclusions
```

The discovery query, root, timestamp, candidates, and confirmation decision are recorded in `initialization/state.json`. If no `--within` root is supplied, the scan uses the configured `engine.source_root`. Global preflight must pass before discovery starts. Candidate confirmation—not discovery authorization—is the user decision that permits domain/submodule creation.

Before a domain exists, the latest metadata-only result is held at the configured `paths.discovery_state` (normally `.workflow/discovery.json`). It is temporary workflow state, not learned knowledge; `module create --from-discovery` attaches it to the new domain.

## Required Artifacts

The domain framework includes:

- `initialization/state.json`: current state, query, discovery root, candidates, and confirmed Build.cs paths.
- `initialization/history.jsonl`: append-only transition events.
- `submodules/index.md`: generated list of confirmed one-to-one submodules.

## Completion Output

Initialization is complete only when the user can see the confirmed domain, the exact submodules, the one-to-one Build.cs mapping, the current domain process state, and the next submodule-selection action.
