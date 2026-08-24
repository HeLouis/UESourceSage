# Agent Protocol

Agents are execution roles, not knowledge storage and not access grants.

## Placement

- Global reusable roles: `skills/ue-source-sage/agents/roles/`.
- Domain-specific roles: `modules/<domain-id>/agents/`.
- Build.cs-scope roles: `modules/<domain-id>/submodules/<submodule-id>/agents/`.

Resolve roles from general to specific, but load only the selected role files. A more specific role may refine output and analysis procedure; it may not weaken global routing, evidence, process, question, or source-allowlist rules.

## Execution

- Use the current agent sequentially by default.
- Start actual subagents only when the environment supports them and the user explicitly requests delegation or parallel agent work.
- Give a subagent the active domain id, submodule id, intent, single allowed Build.cs path, desired artifact, and source access commands.
- Do not pass unrelated module documents or raw engine roots.
- Validate every returned source path against the active submodule before accepting the result.
