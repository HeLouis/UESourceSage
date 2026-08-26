# {{module_name}} Intent Index

| Intent | Goal | Process stages | Preferred evidence |
|---|---|---|---|
| `orient` | Establish scope and navigation | `scope`, `map` | plugin/module descriptors, Build.cs, public headers |
| `explain` | Explain ownership and mechanism | `model` | declarations plus implementation sites |
| `trace` | Follow an end-to-end path | `trace` | ordered call/data references |
| `extend` | Find supported extension points | `model`, `trace`, `verify` | interfaces, registration sites, tests |
| `diagnose` | Explain a failure or surprise | `trace`, `verify` | failing path, guards, logs, repro |
| `compare_version` | Isolate implementation differences | `verify` | version-specific source evidence |
| `review` | Assess learned and unresolved material | `synthesize` | process artifacts and question queue |

