#!/usr/bin/env python3
"""UE Source Sage framework manager. Uses only the Python standard library."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_WORKSPACE = Path(__file__).resolve().parents[3]
MODULE_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
QUESTION_ID_RE = re.compile(r"^Q-(\d{4,})$")
STAGES = ("scope", "map", "model", "trace", "verify", "synthesize")
STAGE_ARTIFACTS = {
    "scope": "process/stages/01-scope.md",
    "map": "process/stages/02-map.md",
    "model": "process/stages/03-model.md",
    "trace": "process/stages/04-trace.md",
    "verify": "process/stages/05-verify.md",
    "synthesize": "process/stages/06-synthesize.md",
}
PROCESS_STATUSES = ("not_started", "in_progress", "blocked", "completed")
QUESTION_STATUSES = ("open", "investigating", "answered", "verified", "archived")
QUESTION_PRIORITIES = ("low", "medium", "high", "critical")
KNOWLEDGE_EVIDENCE_STATUSES = ("draft", "inferred", "verified_source", "experiment_verified", "stale_version")
ROUTE_INTENTS = ("orient", "explain", "trace", "extend", "diagnose", "compare_version", "review")
STAGE_DELIVERABLES = {
    "scope": {"source_boundary", "engine_version", "learning_goal"},
    "map": {"directories", "dependencies", "entry_points"},
    "model": {"concepts", "ownership_lifetime", "invariants", "canonical_document"},
    "trace": {"ordered_flow", "entry_point", "terminal_effect"},
    "verify": {"verification_method", "evidence_cross_check"},
    "synthesize": {"canonical_map", "question_disposition", "next_route"},
}


class UserError(Exception):
    pass


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def workspace(args: argparse.Namespace) -> Path:
    return Path(args.root or DEFAULT_WORKSPACE).expanduser().resolve()


def strip_yaml_comment(text: str) -> str:
    quote: str | None = None
    escaped = False
    for index, char in enumerate(text):
        if escaped:
            escaped = False
            continue
        if char == "\\" and quote == '"':
            escaped = True
            continue
        if char in ("'", '"'):
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
            continue
        if char == "#" and quote is None and (index == 0 or text[index - 1].isspace()):
            return text[:index].rstrip()
    return text.rstrip()


def parse_scalar(value: str) -> Any:
    if value == "{}":
        return {}
    if value.startswith(("'", '"')):
        try:
            return ast.literal_eval(value)
        except (SyntaxError, ValueError) as exc:
            raise UserError(f"Invalid YAML string: {value}") from exc
    lowered = value.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    if lowered in ("null", "~"):
        return None
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?(?:\d+\.\d*|\d*\.\d+)", value):
        return float(value)
    return value


def load_mapping_yaml(path: Path) -> dict[str, Any]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise UserError(f"Missing YAML file: {path}") from exc
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    for line_number, raw in enumerate(lines, start=1):
        prefix = raw[: len(raw) - len(raw.lstrip())]
        if "\t" in prefix:
            raise UserError(f"{path}:{line_number}: YAML indentation cannot contain tabs")
        content = strip_yaml_comment(raw).strip()
        if not content or content == "---":
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_-]*):(?:\s*(.*))?", content)
        if not match:
            raise UserError(f"{path}:{line_number}: expected a YAML mapping entry")
        key, value = match.group(1), match.group(2) or ""
        while stack and indent <= stack[-1][0]:
            stack.pop()
        if not stack:
            raise UserError(f"{path}:{line_number}: invalid indentation")
        parent = stack[-1][1]
        if key in parent:
            raise UserError(f"{path}:{line_number}: duplicate key {key}")
        if value == "":
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = parse_scalar(value)
    return root


def nested(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def resolve_inside(root: Path, relative: str, label: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute():
        raise UserError(f"{label} must be relative to the workspace: {relative}")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise UserError(f"{label} escapes the workspace: {relative}") from exc
    return resolved


def load_config(root: Path) -> dict[str, Any]:
    return load_mapping_yaml(root / "config" / "global.yaml")


def config_problems(root: Path, config: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if nested(config, "schema_version") != 2:
        errors.append("config schema_version must be 2")
    version = nested(config, "engine", "version")
    if not isinstance(version, str) or not version.strip():
        errors.append("engine.version must be a quoted non-empty string")
    source_root = nested(config, "engine", "source_root")
    if not isinstance(source_root, str):
        errors.append("engine.source_root must be a string")
    elif not source_root.strip():
        errors.append("engine.source_root must be configured before any learning workflow can start")
    elif not Path(source_root).expanduser().is_absolute():
        errors.append("engine.source_root must be an absolute path")
    elif not Path(source_root).expanduser().is_dir():
        errors.append(f"engine.source_root does not exist or is inaccessible: {source_root}")
    if not nested(config, "project", "language"):
        errors.append("project.language is required")
    for keys, label in (
        (("paths", "modules"), "paths.modules"),
        (("paths", "module_index"), "paths.module_index"),
        (("paths", "module_template"), "paths.module_template"),
        (("paths", "submodule_template"), "paths.submodule_template"),
        (("paths", "discovery_state"), "paths.discovery_state"),
        (("paths", "active_route_state"), "paths.active_route_state"),
        (("personal_progress", "directory"), "personal_progress.directory"),
    ):
        value = nested(config, *keys)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{label} must be a non-empty relative path")
            continue
        try:
            resolve_inside(root, value, label)
        except UserError as exc:
            errors.append(str(exc))
    if nested(config, "personal_progress", "enabled") not in (True, False):
        errors.append("personal_progress.enabled must be true or false")
    for key in ("max_canonical_docs",):
        value = nested(config, "routing", key)
        if not isinstance(value, int) or value < 0:
            errors.append(f"routing.{key} must be a non-negative integer")
    for template_key in ("module_template", "submodule_template"):
        template_value = nested(config, "paths", template_key)
        if not isinstance(template_value, str) or not template_value:
            continue
        try:
            template = resolve_inside(root, template_value, f"paths.{template_key}")
            if not template.is_dir():
                errors.append(f"module template directory is missing: {template}")
        except UserError:
            pass
    return errors, warnings


def require_config(root: Path) -> dict[str, Any]:
    config = load_config(root)
    errors, _ = config_problems(root, config)
    if errors:
        raise UserError("Invalid global config:\n- " + "\n- ".join(errors))
    return config


def slugify(name: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    if not value:
        raise UserError("Cannot derive an ASCII module id; provide --id")
    return value


def valid_module_id(value: str) -> str:
    result = value.strip().lower()
    if not MODULE_ID_RE.fullmatch(result):
        raise UserError("Module id must use lowercase ASCII letters, digits, and single hyphens")
    return result


def modules_directory(root: Path, config: dict[str, Any]) -> Path:
    return resolve_inside(root, nested(config, "paths", "modules"), "paths.modules")


def module_path(root: Path, config: dict[str, Any], module_id: str) -> Path:
    return modules_directory(root, config) / valid_module_id(module_id)


def require_module(root: Path, config: dict[str, Any], module_id: str) -> Path:
    path = module_path(root, config, module_id)
    if not (path / "module.yaml").is_file():
        raise UserError(f"Module does not exist: {module_id}")
    return path


def submodules_directory(module: Path) -> Path:
    return module / "submodules"


def require_submodule(module: Path, submodule_id: str) -> Path:
    normalized = valid_module_id(submodule_id)
    path = submodules_directory(module) / normalized
    if not (path / "submodule.yaml").is_file():
        raise UserError(f"Submodule does not exist: {module.name}/{normalized}")
    return path


def ensure_scope_engine_version(config: dict[str, Any], scope: Path) -> None:
    expected = str(nested(config, "engine", "version", default="")).strip()
    manifest_name = "module.yaml" if (scope / "module.yaml").is_file() else "submodule.yaml"
    manifest = load_mapping_yaml(scope / manifest_name)
    actual = str(nested(manifest, "engine", "version", default="")).strip()
    if actual != expected:
        raise UserError(
            f"Engine version mismatch for {scope.name}: manifest={actual or '<missing>'}, configured={expected or '<missing>'}. "
            "Update the scope metadata or reinitialize it before continuing."
        )


def ensure_domain_engine_version(config: dict[str, Any], module: Path) -> None:
    ensure_scope_engine_version(config, module)


def require_versioned_submodule(config: dict[str, Any], module: Path, submodule_id: str) -> Path:
    ensure_domain_engine_version(config, module)
    submodule = require_submodule(module, submodule_id)
    ensure_scope_engine_version(config, submodule)
    return submodule


def selected_scope(root: Path, config: dict[str, Any], args: argparse.Namespace) -> Path:
    module = require_module(root, config, args.module)
    ensure_domain_engine_version(config, module)
    submodule_id = getattr(args, "submodule", None)
    return require_versioned_submodule(config, module, submodule_id) if submodule_id else module


def render_template(text: str, values: dict[str, str]) -> str:
    result = text
    for key, value in values.items():
        result = result.replace("{{" + key + "}}", value)
    leftovers = sorted(set(re.findall(r"\{\{([A-Za-z0-9_]+)\}\}", result)))
    if leftovers:
        raise UserError("Unresolved template values: " + ", ".join(leftovers))
    return result


def template_plan(template: Path, values: dict[str, str]) -> list[tuple[Path, str]]:
    result: list[tuple[Path, str]] = []
    for source in sorted(item for item in template.rglob("*") if item.is_file()):
        relative = source.relative_to(template)
        is_template = relative.name.endswith(".tpl")
        target = relative.with_name(relative.name.removesuffix(".tpl")) if is_template else relative
        content = source.read_text(encoding="utf-8")
        result.append((target, render_template(content, values) if is_template else content))
    if not result:
        raise UserError(f"No .tpl files in template directory: {template}")
    return result


def atomic_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    temporary.replace(path)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise UserError(f"Missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise UserError(f"Invalid JSON file: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise UserError(f"Expected a JSON object: {path}")
    return value


def markdown_cell(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def render_modules_index(root: Path, config: dict[str, Any]) -> str:
    modules = modules_directory(root, config)
    rows: list[str] = []
    if modules.is_dir():
        for directory in sorted(modules.iterdir()):
            manifest = directory / "module.yaml"
            if not directory.is_dir() or not manifest.is_file():
                continue
            try:
                data = load_mapping_yaml(manifest)
                module_id = nested(data, "module", "id", default=directory.name)
                name = nested(data, "module", "name", default=directory.name)
                status = nested(data, "module", "status", default="unknown")
                version = nested(data, "engine", "version", default="unknown")
                submodule_count = count_submodules(directory)
            except UserError:
                module_id, name, status, version, submodule_count = directory.name, "INVALID", "invalid", "?", 0
            rows.append(
                f"| `{markdown_cell(module_id)}` | {markdown_cell(name)} | {markdown_cell(status)} | "
                f"{markdown_cell(version)} | {submodule_count} | `{directory.name}/ROUTER.md` |"
            )
    header = (
        "# UE Source Module Index\n\n"
        "> Generated compact module router. Use one primary module per task.\n\n"
        "| Module id | Name | Status | UE version | Submodules | Router |\n"
        "|---|---|---|---|---|---|\n"
    )
    return header + ("\n".join(rows) + "\n" if rows else "")


def write_modules_index(root: Path, config: dict[str, Any]) -> None:
    path = resolve_inside(root, nested(config, "paths", "module_index"), "paths.module_index")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_modules_index(root, config), encoding="utf-8", newline="\n")


def count_submodules(module: Path) -> int:
    directory = submodules_directory(module)
    if not directory.is_dir():
        return 0
    return sum(1 for item in directory.iterdir() if item.is_dir() and (item / "submodule.yaml").is_file())


def render_submodules_index(module: Path) -> str:
    name = scope_display_name(module)
    rows: list[str] = []
    directory = submodules_directory(module)
    if directory.is_dir():
        for item in sorted(directory.iterdir()):
            manifest_path = item / "submodule.yaml"
            if not item.is_dir() or not manifest_path.is_file():
                continue
            manifest = load_mapping_yaml(manifest_path)
            build_cs = nested(manifest, "scope", "build_cs", default="")
            rows.append(
                f"| `{item.name}` | {markdown_cell(nested(manifest, 'submodule', 'name', default=item.name))} | "
                f"{markdown_cell(nested(manifest, 'submodule', 'status', default='unknown'))} | "
                f"`{markdown_cell(build_cs)}` | `{item.name}/ROUTER.md` |"
            )
    header = (
        f"# {name} Submodule Index\n\n"
        "> Generated Build.cs scope router. Select one submodule before accessing Unreal source.\n\n"
        "| Submodule id | Name | Status | Build.cs | Router |\n"
        "|---|---|---|---|---|\n"
    )
    return header + ("\n".join(rows) + "\n" if rows else "")


def write_submodules_index(module: Path) -> None:
    path = submodules_directory(module) / "index.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_submodules_index(module), encoding="utf-8", newline="\n")


def load_process(module: Path) -> dict[str, Any]:
    data = load_json(module / "process" / "state.json")
    if tuple(data.get("stages", {}).keys()) != STAGES:
        raise UserError(f"Invalid process stage set: {module / 'process' / 'state.json'}")
    return data


def append_history(module: Path, event: dict[str, Any]) -> None:
    path = module / "process" / "history.jsonl"
    with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def workspace_from_scope(scope: Path) -> Path:
    current = scope.resolve()
    for candidate in (current, *current.parents):
        if (candidate / "config" / "global.yaml").is_file():
            return candidate
    raise UserError(f"Cannot locate workspace config for scope: {scope}")


def record_stage_transition(
    module: Path,
    stage: str,
    summary: str,
    evidence: list[str],
    work_completed: str,
    exit_assessment: str,
    next_handoff: str,
    deliverables: list[str],
    timestamp: str,
) -> None:
    artifact = module / STAGE_ARTIFACTS[stage]
    with artifact.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write("\n## Recorded Transition\n\n")
        handle.write(f"- Completed at: `{timestamp}`\n")
        handle.write(f"- Summary: {summary}\n")
        handle.write(f"- Work completed: {work_completed}\n")
        handle.write(f"- Exit assessment: {exit_assessment}\n")
        handle.write(f"- Next-stage handoff: {next_handoff}\n")
        handle.write("- Deliverables:\n")
        for item in deliverables:
            handle.write(f"  - `{item}`\n")
        handle.write("- Evidence:\n")
        for item in evidence:
            handle.write(f"  - `{item}`\n")


def stage_exit_problems(module: Path, stage: str, state: dict[str, Any]) -> list[str]:
    current = state["stages"][stage]
    required = ("summary", "work_completed", "exit_assessment", "next_stage_handoff")
    problems = [f"{stage} exit requires {field}" for field in required if not str(current.get(field, "")).strip()]
    if stage == "scope" and (module / "module.yaml").is_file():
        initialization = load_initialization(module)
        if initialization.get("state") != "ready_for_learning":
            problems.append("domain scope cannot exit before Build.cs submodules are confirmed")
    if not current.get("evidence"):
        problems.append(f"{stage} exit requires at least one evidence reference")
    deliverables = set(current.get("deliverables", []))
    missing_deliverables = sorted(STAGE_DELIVERABLES.get(stage, set()) - deliverables)
    if missing_deliverables:
        problems.append(f"{stage} exit is missing deliverables: {', '.join(missing_deliverables)}")
    if stage in ("model", "synthesize") and not knowledge_documents(module):
        problems.append(f"{stage} exit requires at least one canonical knowledge document")
    if stage in ("model", "synthesize"):
        scope_config = load_config(workspace_from_scope(module))
        invalid_documents = {
            document.name: knowledge_document_problems(
                scope_config, module, document
            )
            for document in knowledge_documents(module)
        }
        if invalid_documents and all(items for items in invalid_documents.values()):
            problems.append("all canonical knowledge documents fail quality validation")
    if stage == "verify":
        scope_config = load_config(workspace_from_scope(module))
        verified = False
        for document in knowledge_documents(module):
            metadata = knowledge_metadata(document)
            doc_problems = knowledge_document_problems(
                scope_config, module, document, require_verified=True
            )
            if metadata.get("evidence_status") in {"verified_source", "experiment_verified"} and not doc_problems:
                verified = True
                break
        if not verified:
            problems.append("verify exit requires a canonical document marked verified_source or experiment_verified")
    return problems


def load_questions(module: Path) -> dict[str, Any]:
    data = load_json(module / "questions" / "state.json")
    if not isinstance(data.get("items"), list):
        raise UserError(f"Invalid questions state: {module / 'questions' / 'state.json'}")
    return data


def append_question_history(scope: Path, event: dict[str, Any]) -> None:
    path = scope / "questions" / "history.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def render_question_item(item: dict[str, Any]) -> str:
    evidence = item.get("evidence") or []
    evidence_text = "\n".join(f"- `{value}`" for value in evidence) or "- None yet."
    documents = item.get("documents") or []
    documents_text = "\n".join(f"- `{value}`" for value in documents) or "- None yet."
    answer = item.get("answer") or "Not answered yet."
    status_note = item.get("status_note") or ""
    promoted_from = item.get("promoted_from") or ""
    promoted_to = item.get("promoted_to") or []
    return (
        f"# {item['id']} · {item['question']}\n\n"
        f"- Status: `{item['status']}`\n"
        f"- Priority: `{item['priority']}`\n"
        f"- Topic: `{item['topic']}`\n"
        f"- Discovered in stage: `{item['stage']}`\n"
        f"- Created: `{item['created_at']}`\n"
        f"- Updated: `{item['updated_at']}`\n\n"
        + (f"- Promoted from: `{promoted_from}`\n\n" if promoted_from else "")
        + (f"- Promoted to: `{', '.join(promoted_to)}`\n\n" if promoted_to else "")
        + "## Why Cache This\n\n"
        f"{item['why']}\n\n"
        "## Answer\n\n"
        f"{answer}\n\n"
        "## Evidence\n\n"
        f"{evidence_text}\n\n"
        "## Canonical Documents\n\n"
        f"{documents_text}\n\n"
        "## Status Note\n\n"
        f"{status_note or 'None.'}\n"
    )


def render_questions_index(module_name: str, items: list[dict[str, Any]]) -> str:
    header = (
        f"# {module_name} Questions\n\n"
        "> Generated compact index. Use the question commands; do not edit this file directly.\n\n"
        "| ID | Status | Priority | Stage | Topic | Question |\n"
        "|---|---|---|---|---|---|\n"
    )
    rows = [
        f"| [{item['id']}](items/{item['id']}.md) | {markdown_cell(item['status'])} | "
        f"{markdown_cell(item['priority'])} | {markdown_cell(item['stage'])} | "
        f"{markdown_cell(item['topic'])} | {markdown_cell(item['question'])} |"
        for item in items
    ]
    return header + ("\n".join(rows) + "\n" if rows else "")


def scope_display_name(scope: Path) -> str:
    module_manifest = scope / "module.yaml"
    if module_manifest.is_file():
        return str(nested(load_mapping_yaml(module_manifest), "module", "name", default=scope.name))
    submodule_manifest = scope / "submodule.yaml"
    if submodule_manifest.is_file():
        return str(nested(load_mapping_yaml(submodule_manifest), "submodule", "name", default=scope.name))
    raise UserError(f"Not a learning scope: {scope}")


def knowledge_directory(scope: Path) -> Path:
    return scope / "references" / "knowledge"


def knowledge_metadata(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    metadata: dict[str, str] = {}
    for key in ("id", "title", "topic", "scope", "engine_version", "evidence_status"):
        match = re.search(rf"(?m)^{re.escape(key)}:\s*(.+?)\s*$", text)
        if match:
            metadata[key] = match.group(1).strip().strip('"')
    return metadata


def knowledge_documents(scope: Path) -> list[Path]:
    directory = knowledge_directory(scope)
    if not directory.is_dir():
        return []
    return sorted(path for path in directory.glob("*.md") if path.is_file())


def render_sources_index(scope: Path) -> str:
    header = (
        f"# {scope_display_name(scope)} Sources Index\n\n"
        "> Generated directory of canonical learning documents. Search this file and open only selected documents.\n\n"
        "| ID | Summary | Evidence status | Document |\n"
        "|---|---|---|---|\n"
    )
    rows: list[str] = []
    for path in knowledge_documents(scope):
        metadata = knowledge_metadata(path)
        document = f"../knowledge/{path.name}"
        rows.append(
            f"| `{markdown_cell(metadata.get('id', path.stem))}` | {markdown_cell(metadata.get('title', path.stem))} | "
            f"{markdown_cell(metadata.get('evidence_status', 'draft'))} | `{document}` |"
        )
    return header + ("\n".join(rows) + "\n" if rows else "")


def write_sources_index(scope: Path) -> None:
    path = scope / "references" / "indexes" / "sources.index.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_sources_index(scope), encoding="utf-8", newline="\n")


def validate_knowledge_document_path(scope: Path, value: str) -> str:
    normalized = value.strip().replace("\\", "/")
    if not normalized:
        raise UserError("Canonical document path cannot be empty")
    candidate = (scope / normalized).resolve()
    try:
        candidate.relative_to(knowledge_directory(scope).resolve())
    except ValueError as exc:
        raise UserError("Canonical document must be inside references/knowledge") from exc
    if candidate.suffix.lower() != ".md" or not candidate.is_file():
        raise UserError(f"Canonical document does not exist: {value}")
    return candidate.relative_to(scope).as_posix()


def knowledge_section(text: str, heading: str) -> str:
    match = re.search(
        rf"(?ms)^##\s+{re.escape(heading)}\s*$\n(.*?)(?=^##\s+|\Z)",
        text,
    )
    return match.group(1).strip() if match else ""


def knowledge_source_entries(text: str) -> list[str]:
    section = knowledge_section(text, "Source Trail")
    return [match.group(1).strip() for match in re.finditer(r"(?m)^-\s+`([^`]+)`\s*$", section)]


def knowledge_document_problems(
    config: dict[str, Any], scope: Path, path: Path, require_verified: bool = False
) -> list[str]:
    problems: list[str] = []
    text = path.read_text(encoding="utf-8")
    metadata = knowledge_metadata(path)
    required_metadata = ("id", "title", "topic", "scope", "engine_version", "evidence_status")
    for field in required_metadata:
        if not metadata.get(field):
            problems.append(f"missing metadata: {field}")
    if re.search(r"\{\{[^}]+\}\}", text):
        problems.append("contains unresolved template placeholders")
    if not knowledge_section(text, "Quick Answer"):
        problems.append("Quick Answer is empty")
    sources = knowledge_source_entries(text)
    if not sources:
        problems.append("Source Trail is empty")
    if metadata.get("scope") != scope.name:
        problems.append(f"scope metadata is {metadata.get('scope')!r}, expected {scope.name!r}")
    expected_version = str(nested(config, "engine", "version"))
    if metadata.get("engine_version") != expected_version and metadata.get("evidence_status") != "stale_version":
        problems.append(
            f"engine version mismatch (document={metadata.get('engine_version') or '<missing>'}, configured={expected_version})"
        )
    if metadata.get("evidence_status") not in KNOWLEDGE_EVIDENCE_STATUSES:
        problems.append(f"invalid evidence status: {metadata.get('evidence_status')}")
    if require_verified and metadata.get("evidence_status") not in {"verified_source", "experiment_verified"}:
        problems.append("verification stage requires verified_source or experiment_verified evidence status")
    if (scope / "submodule.yaml").is_file() and sources:
        try:
            engine_root, source_root, exact = submodule_scope_paths(config, scope)
            for value in sources:
                source_path = re.split(r"[#:]", value, maxsplit=1)[0].strip()
                candidate = is_allowed_source_path(engine_root, source_root, exact, source_path)
                if not candidate.is_file():
                    problems.append(f"source trail path does not exist: {source_path}")
        except UserError as exc:
            problems.append(str(exc))
    elif (scope / "module.yaml").is_file() and sources:
        for value in sources:
            source_path = re.split(r"[#:]", value, maxsplit=1)[0].strip()
            candidate = (scope / source_path).resolve()
            try:
                candidate.relative_to(scope.resolve())
            except ValueError:
                problems.append(f"domain source trail escapes the domain: {source_path}")
                continue
            if not candidate.is_file():
                problems.append(f"domain source trail path does not exist: {source_path}")
    return problems


def link_question_to_documents(scope: Path, question_id: str, documents: list[str]) -> None:
    marker = f"- `{question_id}`"
    for relative in documents:
        path = scope / relative
        text = path.read_text(encoding="utf-8")
        if marker in text:
            continue
        heading = "## Linked Questions\n"
        if heading in text:
            text = text.replace(heading, heading + "\n" + marker + "\n", 1)
        else:
            text = text.rstrip() + "\n\n## Linked Questions\n\n" + marker + "\n"
        path.write_text(text, encoding="utf-8", newline="\n")


def write_question_views(module: Path, state: dict[str, Any]) -> None:
    items_dir = module / "questions" / "items"
    items_dir.mkdir(parents=True, exist_ok=True)
    for item in state["items"]:
        (items_dir / f"{item['id']}.md").write_text(
            render_question_item(item), encoding="utf-8", newline="\n"
        )
    (module / "questions" / "index.md").write_text(
        render_questions_index(scope_display_name(module), state["items"]),
        encoding="utf-8",
        newline="\n",
    )


def find_question(state: dict[str, Any], question_id: str) -> dict[str, Any]:
    normalized = question_id.strip().upper()
    if not QUESTION_ID_RE.fullmatch(normalized):
        raise UserError("Question id must look like Q-0001")
    for item in state["items"]:
        if item.get("id") == normalized:
            return item
    raise UserError(f"Question does not exist: {normalized}")


def validate_learning_scope(
    scope: Path,
    manifest_name: str,
    identity_section: str,
    expected_engine_version: str | None = None,
    config: dict[str, Any] | None = None,
) -> list[str]:
    errors: list[str] = []
    required = [
        manifest_name,
        "ROUTER.md",
        "references/indexes/routing.index.md",
        "references/indexes/intents.index.md",
        "references/indexes/topics.index.md",
        "references/indexes/constraints.index.md",
        "references/indexes/boundaries.index.md",
        "references/indexes/ambiguous-symbols.index.md",
        "references/indexes/sources.index.md",
        "process/workflow.yaml",
        "process/state.json",
        "process/history.jsonl",
        "questions/state.json",
        "questions/index.md",
        "questions/history.jsonl",
        "validation/routing-scenarios.md",
    ] + list(STAGE_ARTIFACTS.values())
    for relative in required:
        if not (scope / relative).is_file():
            errors.append(f"{scope.name}: missing {relative}")
    for relative in ("roles", "references/sources", "references/knowledge", "questions/items"):
        if not (scope / relative).is_dir():
            errors.append(f"{scope.name}: missing directory {relative}")
    if errors:
        return errors
    try:
        manifest = load_mapping_yaml(scope / manifest_name)
        if nested(manifest, identity_section, "id") != scope.name:
            errors.append(f"{scope.name}: {manifest_name} id must match directory name")
        manifest_version = str(nested(manifest, "engine", "version", default="")).strip()
        if expected_engine_version and manifest_version != expected_engine_version:
            errors.append(
                f"{scope.name}: engine version mismatch (manifest={manifest_version or '<missing>'}, "
                f"configured={expected_engine_version})"
            )
        process = load_process(scope)
        if process.get("module_id") != scope.name:
            errors.append(f"{scope.name}: process scope id mismatch")
        expected_kind = "domain" if manifest_name == "module.yaml" else "submodule"
        if process.get("scope_kind") != expected_kind:
            errors.append(f"{scope.name}: process scope_kind must be {expected_kind}")
        if process.get("status") not in PROCESS_STATUSES:
            errors.append(f"{scope.name}: invalid process status")
        if process.get("current_stage") not in STAGES:
            errors.append(f"{scope.name}: invalid current process stage")
        for stage, value in process["stages"].items():
            if value.get("status") not in PROCESS_STATUSES:
                errors.append(f"{scope.name}: invalid status for stage {stage}")
            for field in ("summary", "work_completed", "exit_assessment", "next_stage_handoff"):
                if field not in value or not isinstance(value.get(field), str):
                    errors.append(f"{scope.name}: missing process field {stage}.{field}")
            if not isinstance(value.get("deliverables", []), list):
                errors.append(f"{scope.name}: process field {stage}.deliverables must be a list")
        questions = load_questions(scope)
        if questions.get("module_id") != scope.name:
            errors.append(f"{scope.name}: questions scope id mismatch")
        if questions.get("scope_kind") != expected_kind:
            errors.append(f"{scope.name}: questions scope_kind must be {expected_kind}")
        seen: set[str] = set()
        for item in questions["items"]:
            question_id = item.get("id", "")
            if not QUESTION_ID_RE.fullmatch(question_id) or question_id in seen:
                errors.append(f"{scope.name}: invalid or duplicate question id {question_id}")
            seen.add(question_id)
            if item.get("status") not in QUESTION_STATUSES:
                errors.append(f"{scope.name}: invalid question status for {question_id}")
            if item.get("stage") not in STAGES:
                errors.append(f"{scope.name}: invalid discovery stage for {question_id}")
            if item.get("status") in ("answered", "verified") and (
                not item.get("answer") or not item.get("evidence")
            ):
                errors.append(f"{scope.name}: answered question {question_id} lacks answer/evidence")
            if not isinstance(item.get("documents", []), list):
                errors.append(f"{scope.name}: question {question_id} documents must be a list")
            else:
                for document in item.get("documents", []):
                    try:
                        validate_knowledge_document_path(scope, str(document))
                    except UserError as exc:
                        errors.append(f"{scope.name}: question {question_id}: {exc}")
            if item.get("status") == "verified" and not item.get("documents"):
                errors.append(f"{scope.name}: verified question {question_id} must link a canonical document")
            if not isinstance(item.get("promoted_to", []), list):
                errors.append(f"{scope.name}: question {question_id} promoted_to must be a list")
        expected_index = render_questions_index(scope_display_name(scope), questions["items"])
        actual_index = (scope / "questions" / "index.md").read_text(encoding="utf-8")
        if actual_index != expected_index:
            errors.append(f"{scope.name}: questions/index.md is stale; run question rebuild")
        for item in questions["items"]:
            item_path = scope / "questions" / "items" / f"{item['id']}.md"
            if not item_path.is_file() or item_path.read_text(encoding="utf-8") != render_question_item(item):
                errors.append(f"{scope.name}: rendered question item is stale: {item['id']}")
        expected_sources = render_sources_index(scope)
        actual_sources = (scope / "references" / "indexes" / "sources.index.md").read_text(encoding="utf-8")
        if actual_sources != expected_sources:
            errors.append(f"{scope.name}: sources.index.md is stale; run knowledge rebuild-index")
        if expected_engine_version:
            for document in knowledge_documents(scope):
                metadata = knowledge_metadata(document)
                document_version = metadata.get("engine_version", "")
                if document_version != expected_engine_version and metadata.get("evidence_status") != "stale_version":
                    errors.append(
                        f"{scope.name}: knowledge document {document.name} engine version mismatch "
                        f"(document={document_version or '<missing>'}, configured={expected_engine_version})"
                    )
                errors.extend(
                    f"{scope.name}: knowledge document {document.name}: {problem}"
                    for problem in knowledge_document_problems(
                        config or {"engine": {"version": expected_engine_version}}, scope, document
                    )
                )
    except UserError as exc:
        errors.append(f"{scope.name}: {exc}")
    return errors


def validate_submodule(
    module: Path,
    submodule: Path,
    expected_engine_version: str | None = None,
    config: dict[str, Any] | None = None,
) -> list[str]:
    errors = validate_learning_scope(submodule, "submodule.yaml", "submodule", expected_engine_version, config)
    if errors:
        return errors
    try:
        manifest = load_mapping_yaml(submodule / "submodule.yaml")
        if nested(manifest, "submodule", "parent_module") != module.name:
            errors.append(f"{submodule.name}: parent_module must be {module.name}")
        if nested(manifest, "scope", "access_policy") != "allowlist_only":
            errors.append(f"{submodule.name}: access_policy must be allowlist_only")
        if nested(manifest, "routing", "dependency_grants_access") is not False:
            errors.append(f"{submodule.name}: dependency_grants_access must be false")
        build_cs = nested(manifest, "scope", "build_cs")
        if not isinstance(build_cs, str) or not build_cs.replace("\\", "/").endswith(".Build.cs"):
            errors.append(f"{submodule.name}: exactly one valid Build.cs path is required")
        if nested(manifest, "scope", "source_root_from_build_cs") is not True:
            errors.append(f"{submodule.name}: source_root_from_build_cs must be true")
        allowed_files = nested(manifest, "scope", "allowed_files", default={})
        if not isinstance(allowed_files, dict):
            errors.append(f"{submodule.name}: allowed_files must be a mapping")
    except UserError as exc:
        errors.append(f"{submodule.name}: {exc}")
    return errors


def validate_module(
    module: Path, expected_engine_version: str | None = None, config: dict[str, Any] | None = None
) -> list[str]:
    errors = validate_learning_scope(module, "module.yaml", "module", expected_engine_version, config)
    for relative in ("initialization/state.json", "initialization/history.jsonl"):
        if not (module / relative).is_file():
            errors.append(f"{module.name}: missing {relative}")
    if not (module / "submodules" / "index.md").is_file():
        errors.append(f"{module.name}: missing submodules/index.md")
        return errors
    try:
        initialization = load_initialization(module)
        allowed_states = {
            "requested", "awaiting_engine_config", "domain_created", "awaiting_build_scope",
            "candidate_confirmation_required", "submodules_registered",
            "ready_for_learning", "blocked",
        }
        if initialization.get("domain_id") != module.name:
            errors.append(f"{module.name}: initialization domain_id mismatch")
        if initialization.get("state") not in allowed_states:
            errors.append(f"{module.name}: invalid initialization state")
        if not isinstance(initialization.get("candidates"), list):
            errors.append(f"{module.name}: initialization candidates must be a list")
        if not isinstance(initialization.get("confirmed_build_cs"), list):
            errors.append(f"{module.name}: confirmed_build_cs must be a list")
        if not isinstance(initialization.get("confirmed_submodules"), list):
            errors.append(f"{module.name}: confirmed_submodules must be a list")
    except UserError as exc:
        errors.append(f"{module.name}: {exc}")
    expected_index = render_submodules_index(module)
    if (module / "submodules" / "index.md").read_text(encoding="utf-8") != expected_index:
        errors.append(f"{module.name}: submodules/index.md is stale; run submodule rebuild-index")
    directory = submodules_directory(module)
    if directory.is_dir():
        for item in sorted(directory.iterdir()):
            if item.is_dir() and (item / "submodule.yaml").is_file():
                errors.extend(validate_submodule(module, item, expected_engine_version, config))
    return errors


def validate_skill(root: Path) -> list[str]:
    errors: list[str] = []
    skill = root / "skills" / "ue-source-sage"
    skill_file = skill / "SKILL.md"
    if not skill_file.is_file():
        return ["missing skills/ue-source-sage/SKILL.md"]
    text = skill_file.read_text(encoding="utf-8")
    match = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n", text, re.DOTALL)
    if not match:
        errors.append("SKILL.md must start with YAML frontmatter")
    else:
        frontmatter: dict[str, str] = {}
        for line in match.group(1).splitlines():
            key, separator, value = line.partition(":")
            if not separator:
                errors.append(f"invalid SKILL.md frontmatter line: {line}")
                continue
            frontmatter[key.strip()] = value.strip()
        if set(frontmatter) != {"name", "description"}:
            errors.append("SKILL.md frontmatter must contain only name and description")
        if frontmatter.get("name") != "ue-source-sage":
            errors.append("SKILL.md name must be ue-source-sage")
        description = frontmatter.get("description", "")
        if not description or "TODO" in description or len(description) > 1024:
            errors.append("SKILL.md description is missing, unfinished, or too long")
    if "TODO" in text:
        errors.append("SKILL.md contains TODO placeholders")
    for relative in (
        "skill-ui.yaml",
        "scripts/sage.py",
        "references/module-contract.md",
        "references/process-protocol.md",
        "references/questions-protocol.md",
        "references/routing-protocol.md",
        "references/role-protocol.md",
        "references/domain-initialization.md",
        "references/initialization-prompts.md",
        "assets/module-template/module.yaml.tpl",
        "assets/submodule-template/submodule.yaml.tpl",
        "roles/boundary-guard.md",
        "roles/source-mapper.md",
        "roles/callflow-tracer.md",
        "roles/question-curator.md",
        "assets/module-template/initialization/state.json.tpl",
        "assets/module-template/initialization/history.jsonl.tpl",
        "assets/module-template/references/knowledge/.gitkeep",
        "assets/module-template/questions/history.jsonl.tpl",
    ):
        if not (skill / relative).is_file():
            errors.append(f"skill is missing {relative}")
    ui_metadata_path = skill / "skill-ui.yaml"
    if ui_metadata_path.is_file():
        try:
            metadata = load_mapping_yaml(ui_metadata_path)
            short = nested(metadata, "interface", "short_description")
            prompt = nested(metadata, "interface", "default_prompt")
            if not isinstance(short, str) or not 25 <= len(short) <= 64:
                errors.append("skill-ui.yaml short_description must be 25-64 characters")
            if not isinstance(prompt, str) or "$ue-source-sage" not in prompt:
                errors.append("skill-ui.yaml default_prompt must mention $ue-source-sage")
        except UserError as exc:
            errors.append(f"invalid skill-ui.yaml: {exc}")
    return errors


def command_validate(args: argparse.Namespace) -> int:
    root = workspace(args)
    config = load_config(root)
    errors, warnings = config_problems(root, config)
    for warning in warnings:
        print(f"Warning: {warning}")
    errors.extend(validate_skill(root))
    if not errors:
        active_path = active_route_path(root, config)
        if active_path.is_file():
            try:
                route = load_json(active_path)
                if route.get("engine_version") != str(nested(config, "engine", "version")):
                    errors.append("active route engine version is stale; clear or reactivate the route")
                if not route.get("domain_id") or not route.get("submodule_id") or not route.get("generation"):
                    errors.append("active route is missing domain, submodule, or generation")
                if route.get("domain_id") and route.get("submodule_id"):
                    active_module = require_module(root, config, str(route["domain_id"]))
                    active_submodule = require_submodule(active_module, str(route["submodule_id"]))
                    source_index = active_submodule / "references" / "indexes" / "sources.index.md"
                    if source_index.is_file() and route.get("sources_index_digest") != file_digest(source_index):
                        errors.append("active route sources index is stale; reactivate the route")
            except UserError as exc:
                errors.append(str(exc))
        modules = modules_directory(root, config)
        if modules.is_dir():
            for directory in sorted(modules.iterdir()):
                if directory.is_dir() and (directory / "module.yaml").is_file():
                    errors.extend(
                        validate_module(
                            directory,
                            str(nested(config, "engine", "version", default="")).strip(),
                            config,
                        )
                    )
        index_path = resolve_inside(root, nested(config, "paths", "module_index"), "paths.module_index")
        expected = render_modules_index(root, config)
        if not index_path.is_file() or index_path.read_text(encoding="utf-8") != expected:
            errors.append("modules/index.md is missing or stale; run module rebuild-index")
    if errors:
        for error in errors:
            print(f"Error: {error}", file=sys.stderr)
        return 1
    print("UE Source Sage framework validation passed.")
    return 0


def command_preflight(args: argparse.Namespace) -> int:
    root = workspace(args)
    config = load_config(root)
    errors, warnings = config_problems(root, config)
    for warning in warnings:
        print(f"Warning: {warning}")
    if errors:
        for error in errors:
            print(f"Error: {error}", file=sys.stderr)
        return 1
    print("Global configuration preflight passed. Learning workflow is unlocked.")
    return 0


def command_module_create(args: argparse.Namespace) -> int:
    root = workspace(args)
    config = require_config(root)
    name = args.name.strip()
    if not name:
        raise UserError("Module name cannot be empty")
    module_id = valid_module_id(args.id or slugify(name))
    destination = module_path(root, config, module_id)
    if destination.exists():
        raise UserError(f"Module already exists and will not be overwritten: {destination}")
    values = {
        "module_id": module_id,
        "module_name": name,
        "scope_kind": "domain",
        "domain_id": module_id,
        "submodule_id": "",
        "created_at": now_utc(),
        "engine_version": str(nested(config, "engine", "version")),
        "max_canonical_docs": str(nested(config, "routing", "max_canonical_docs")),
    }
    discovery = None
    if args.from_discovery:
        discovery_path = resolve_inside(root, nested(config, "paths", "discovery_state"), "paths.discovery_state")
        discovery = load_json(discovery_path)
        if not discovery.get("candidates"):
            raise UserError("No discovery candidates are available for --from-discovery")
    template = resolve_inside(root, nested(config, "paths", "module_template"), "paths.module_template")
    plan = template_plan(template, values)
    if args.dry_run:
        print(f"Would create empty module framework: {destination}")
        for relative, _ in plan:
            print(f"  {relative.as_posix()}")
        return 0
    for relative, content in plan:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
    write_question_views(destination, load_questions(destination))
    write_sources_index(destination)
    write_submodules_index(destination)
    initialization = load_initialization(destination)
    initialization_state = "awaiting_build_scope"
    timestamp = now_utc()
    initialization["state"] = initialization_state
    initialization["updated_at"] = timestamp
    if args.from_discovery:
        initialization.update({
            "state": "candidate_confirmation_required",
            "query": discovery.get("query"),
            "discovery_root": discovery.get("discovery_root"),
            "discovery_mode": discovery.get("discovery_mode"),
            "candidates": discovery.get("candidates", []),
        })
    atomic_json(destination / "initialization" / "state.json", initialization)
    append_initialization_history(destination, {
        "at": timestamp,
        "event": "initialization_waiting",
        "state": initialization_state,
    })
    if args.from_discovery:
        append_initialization_history(destination, {
            "at": timestamp,
            "event": "discovery_attached",
            "state": "candidate_confirmation_required",
        })
    write_modules_index(root, config)
    print(f"Created empty module framework: {destination}")
    return 0


def yaml_mapping_entries(values: list[str], prefix: str) -> str:
    return "\n".join(
        f"    {prefix}{index:02d}: {json.dumps(value, ensure_ascii=False)}"
        for index, value in enumerate(values, start=1)
    )


def source_root_for_build_cs(engine_root: Path, build_cs: str) -> Path:
    relative = build_cs.replace("\\", "/")
    if not relative.endswith(".Build.cs"):
        raise UserError(f"Build.cs path must end with .Build.cs: {build_cs}")
    path = (engine_root / relative).resolve()
    try:
        path.relative_to(engine_root.resolve())
    except ValueError as exc:
        raise UserError(f"Build.cs escapes engine.source_root: {build_cs}") from exc
    return path


def command_submodule_create(args: argparse.Namespace) -> int:
    root = workspace(args)
    config = require_config(root)
    module = require_module(root, config, args.module)
    ensure_domain_engine_version(config, module)
    name = args.name.strip()
    if not name:
        raise UserError("Submodule name cannot be empty")
    submodule_id = valid_module_id(args.id or slugify(name))
    destination = submodules_directory(module) / submodule_id
    if destination.exists():
        raise UserError(f"Submodule already exists and will not be overwritten: {destination}")
    build_cs = args.build_cs.strip().replace("\\", "/")
    if not build_cs:
        raise UserError("Exactly one --build-cs is required")
    existing_builds = {
        str(nested(load_mapping_yaml(item / "submodule.yaml"), "scope", "build_cs", default="")).replace("\\", "/")
        for item in submodules_directory(module).iterdir()
        if item.is_dir() and (item / "submodule.yaml").is_file()
    } if submodules_directory(module).is_dir() else set()
    if build_cs in existing_builds:
        raise UserError(f"Build.cs already belongs to an existing submodule: {build_cs}")
    engine_source = str(nested(config, "engine", "source_root", default="")).strip()
    if engine_source:
        engine_root = Path(engine_source).expanduser().resolve()
        if not engine_root.is_dir():
            raise UserError(f"engine.source_root is not accessible: {engine_root}")
        build_path = source_root_for_build_cs(engine_root, build_cs)
        if not build_path.is_file():
            raise UserError(f"Build.cs does not exist: {build_path}")
    allowed_files = [value.strip().replace("\\", "/") for value in args.allow_file if value.strip()]
    values = {
        "module_id": submodule_id,
        "module_name": name,
        "scope_kind": "submodule",
        "domain_id": module.name,
        "submodule_id": submodule_id,
        "submodule_id": submodule_id,
        "submodule_name": name,
        "parent_module_id": module.name,
        "created_at": now_utc(),
        "engine_version": str(nested(config, "engine", "version")),
        "max_canonical_docs": str(nested(config, "routing", "max_canonical_docs")),
        "build_cs": build_cs,
        "allowed_files_block": " {}" if not allowed_files else "\n" + yaml_mapping_entries(allowed_files, "file_"),
    }
    template = resolve_inside(root, nested(config, "paths", "submodule_template"), "paths.submodule_template")
    module_template = resolve_inside(root, nested(config, "paths", "module_template"), "paths.module_template")
    plan = template_plan(template, values)
    # Reuse the generic process/questions/index assets, but give them the submodule identity.
    shared = template_plan_selected(
        module_template,
        values,
        ("references", "process", "questions"),
    )
    plan.extend(shared)
    if args.dry_run:
        print(f"Would create Build.cs-scoped submodule: {destination}")
        for relative, _ in plan:
            print(f"  {relative.as_posix()}")
        return 0
    for relative, content in plan:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
    write_question_views(destination, load_questions(destination))
    write_sources_index(destination)
    write_submodules_index(module)
    write_modules_index(root, config)
    if getattr(args, "register_initialization", True):
        initialization = load_initialization(module)
        timestamp = now_utc()
        initialization["state"] = "ready_for_learning"
        initialization["confirmed_build_cs"] = list(initialization.get("confirmed_build_cs", [])) + [build_cs]
        initialization["confirmed_submodules"] = list(initialization.get("confirmed_submodules", [])) + [submodule_id]
        initialization["updated_at"] = timestamp
        atomic_json(module / "initialization" / "state.json", initialization)
        append_initialization_history(module, {
            "at": timestamp,
            "event": "submodule_registered",
            "build_cs": build_cs,
            "submodule": submodule_id,
            "source": "explicit_build_cs",
        })
    print(f"Created Build.cs-scoped submodule: {destination}")
    return 0


def template_plan_selected(template: Path, values: dict[str, str], roots: tuple[str, ...]) -> list[tuple[Path, str]]:
    result: list[tuple[Path, str]] = []
    for root_name in roots:
        source_root = template / root_name
        if not source_root.is_dir():
            raise UserError(f"Missing shared template directory: {source_root}")
        for source in sorted(item for item in source_root.rglob("*") if item.is_file()):
            relative = source.relative_to(template)
            is_template = relative.name.endswith(".tpl")
            target = relative.with_name(relative.name.removesuffix(".tpl")) if is_template else relative
            content = source.read_text(encoding="utf-8")
            result.append((target, render_template(content, values) if is_template else content))
    return result


def command_submodule_list(args: argparse.Namespace) -> int:
    root = workspace(args)
    config = require_config(root)
    module = require_module(root, config, args.module)
    ensure_domain_engine_version(config, module)
    found = False
    directory = submodules_directory(module)
    if directory.is_dir():
        for item in sorted(directory.iterdir()):
            if item.is_dir() and (item / "submodule.yaml").is_file():
                found = True
                manifest = load_mapping_yaml(item / "submodule.yaml")
                build_cs = nested(manifest, "scope", "build_cs", default="")
                print(f"{item.name}\t{nested(manifest, 'submodule', 'name')}\t{build_cs}")
    if not found:
        print(f"No submodules have been created for {module.name}.")
    return 0


def command_submodule_rebuild_index(args: argparse.Namespace) -> int:
    root = workspace(args)
    config = require_config(root)
    module = require_module(root, config, args.module)
    ensure_domain_engine_version(config, module)
    write_submodules_index(module)
    print(f"Rebuilt submodule index for {module.name}.")
    return 0


def command_knowledge_create(args: argparse.Namespace) -> int:
    root = workspace(args)
    config = require_config(root)
    scope = selected_scope(root, config, args)
    title = " ".join(args.title.split())
    if not title:
        raise UserError("Knowledge document title cannot be empty")
    document_id = valid_module_id(args.id or slugify(title))
    path = knowledge_directory(scope) / f"{document_id}.md"
    if path.exists():
        raise UserError(f"Knowledge document already exists: {path}")
    topic = " ".join(args.topic.split()) or "general"
    answer = args.answer.strip() if args.answer else ""
    sources = [value.strip().replace("\\", "/") for value in args.source if value.strip()]
    questions = [value.strip().upper() for value in args.question_id if value.strip()]
    if not answer:
        raise UserError("Canonical knowledge creation requires a non-empty --answer")
    if not sources:
        raise UserError("Canonical knowledge creation requires at least one --source")
    if (scope / "submodule.yaml").is_file():
        engine_root, source_root, exact = submodule_scope_paths(config, scope)
        for value in sources:
            source_path = re.split(r"[#:]", value, maxsplit=1)[0].strip()
            candidate = is_allowed_source_path(engine_root, source_root, exact, source_path)
            if not candidate.is_file():
                raise UserError(f"Knowledge source trail path does not exist: {source_path}")
    else:
        for value in sources:
            source_path = re.split(r"[#:]", value, maxsplit=1)[0].strip()
            candidate = (scope / source_path).resolve()
            try:
                candidate.relative_to(scope.resolve())
            except ValueError as exc:
                raise UserError(f"Domain knowledge source trail escapes the domain: {source_path}") from exc
            if not candidate.is_file():
                raise UserError(f"Domain knowledge source trail path does not exist: {source_path}")
    question_state = load_questions(scope)
    for question_id in questions:
        find_question(question_state, question_id)
    version = str(nested(config, "engine", "version"))
    content = (
        "---\n"
        f"id: {document_id}\n"
        f"title: {json.dumps(title, ensure_ascii=False)}\n"
        f"topic: {json.dumps(topic, ensure_ascii=False)}\n"
        f"scope: {scope.name}\n"
        f"engine_version: {json.dumps(version, ensure_ascii=False)}\n"
        f"evidence_status: {args.evidence_status}\n"
        "---\n\n"
        f"# {title}\n\n"
        "## Quick Answer\n\n"
        f"{answer}\n\n"
        "## Source Trail\n\n"
        + ("\n".join(f"- `{value}`" for value in sources) if sources else "- Add ordered source paths and symbols.")
        + "\n\n## Mechanism\n\n"
        "Describe the mechanism in execution or data-flow order.\n\n"
        "## Boundaries And Misconceptions\n\n"
        "Record what this document does not cover and common incorrect assumptions.\n\n"
        "## Linked Questions\n\n"
        + ("\n".join(f"- `{value}`" for value in questions) if questions else "- None yet.")
        + "\n"
    )
    if args.dry_run:
        print(f"Would create canonical knowledge document: {path}")
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    problems = knowledge_document_problems(config, scope, path)
    if problems:
        path.unlink()
        raise UserError("Created document is invalid:\n- " + "\n- ".join(problems))
    write_sources_index(scope)
    invalidate_active_route(root, config)
    print(f"Created canonical knowledge document: {path}")
    return 0


def command_knowledge_rebuild_index(args: argparse.Namespace) -> int:
    root = workspace(args)
    config = require_config(root)
    scope = selected_scope(root, config, args)
    write_sources_index(scope)
    invalidate_active_route(root, config)
    print(f"Rebuilt sources index for {scope.name}.")
    return 0


def knowledge_document_path(scope: Path, document_id: str) -> Path:
    normalized = valid_module_id(document_id)
    path = knowledge_directory(scope) / f"{normalized}.md"
    if not path.is_file():
        raise UserError(f"Canonical document does not exist: {document_id}")
    return path


def replace_frontmatter_value(text: str, key: str, value: str) -> str:
    pattern = rf"(?m)^{re.escape(key)}:\s*.*$"
    if not re.search(pattern, text):
        raise UserError(f"Canonical document is missing metadata: {key}")
    return re.sub(pattern, f"{key}: {json.dumps(value, ensure_ascii=False)}", text, count=1)


def replace_knowledge_section(text: str, heading: str, body: str) -> str:
    pattern = rf"(?ms)^(##\s+{re.escape(heading)}\s*$\n).*?(?=^##\s+|\Z)"
    if not re.search(pattern, text):
        raise UserError(f"Canonical document is missing section: {heading}")
    return re.sub(pattern, rf"\1{body.rstrip()}\n\n", text, count=1)


def command_knowledge_update(args: argparse.Namespace) -> int:
    root = workspace(args)
    config = require_config(root)
    scope = selected_scope(root, config, args)
    path = knowledge_document_path(scope, args.document_id)
    text = path.read_text(encoding="utf-8")
    if args.title:
        title = " ".join(args.title.split())
        text = replace_frontmatter_value(text, "title", title)
        text = re.sub(r"(?m)^#\s+.*$", f"# {title}", text, count=1)
    if args.topic:
        text = replace_frontmatter_value(text, "topic", " ".join(args.topic.split()))
    if args.answer:
        text = replace_knowledge_section(text, "Quick Answer", args.answer.strip())
    if args.evidence_status:
        text = replace_frontmatter_value(text, "evidence_status", args.evidence_status)
    sources = [value.strip().replace("\\", "/") for value in args.source if value.strip()]
    if sources:
        if (scope / "submodule.yaml").is_file():
            engine_root, source_root, exact = submodule_scope_paths(config, scope)
            for value in sources:
                source_path = re.split(r"[#:]", value, maxsplit=1)[0].strip()
                candidate = is_allowed_source_path(engine_root, source_root, exact, source_path)
                if not candidate.is_file():
                    raise UserError(f"Knowledge source trail path does not exist: {source_path}")
        else:
            for value in sources:
                source_path = re.split(r"[#:]", value, maxsplit=1)[0].strip()
                candidate = (scope / source_path).resolve()
                try:
                    candidate.relative_to(scope.resolve())
                except ValueError as exc:
                    raise UserError(f"Domain knowledge source trail escapes the domain: {source_path}") from exc
                if not candidate.is_file():
                    raise UserError(f"Domain knowledge source trail path does not exist: {source_path}")
        existing = knowledge_source_entries(text)
        combined = existing + [value for value in sources if value not in existing]
        text = replace_knowledge_section(text, "Source Trail", "\n".join(f"- `{value}`" for value in combined))
    if args.question_id:
        state = load_questions(scope)
        for question_id in args.question_id:
            find_question(state, question_id.strip().upper())
        linked = knowledge_section(text, "Linked Questions")
        existing = [match.group(1).strip().upper() for match in re.finditer(r"(?m)^-\s+`([^`]+)`", linked)]
        combined = existing + [value.strip().upper() for value in args.question_id if value.strip() and value.strip().upper() not in existing]
        text = replace_knowledge_section(text, "Linked Questions", "\n".join(f"- `{value}`" for value in combined))
    if args.dry_run:
        print(f"Would update canonical knowledge document: {path}")
        return 0
    original_text = path.read_text(encoding="utf-8")
    path.write_text(text, encoding="utf-8", newline="\n")
    problems = knowledge_document_problems(config, scope, path)
    if problems:
        path.write_text(original_text, encoding="utf-8", newline="\n")
        raise UserError("Updated document is invalid:\n- " + "\n- ".join(problems))
    write_sources_index(scope)
    invalidate_active_route(root, config)
    print(f"Updated canonical knowledge document: {path}")
    return 0


def command_knowledge_archive(args: argparse.Namespace) -> int:
    root = workspace(args)
    config = require_config(root)
    scope = selected_scope(root, config, args)
    path = knowledge_document_path(scope, args.document_id)
    archive_dir = knowledge_directory(scope) / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    target = archive_dir / path.name
    if target.exists():
        raise UserError(f"Archived canonical document already exists: {target}")
    if args.dry_run:
        print(f"Would archive canonical knowledge document: {path} -> {target}")
        return 0
    archived_text = path.read_text(encoding="utf-8")
    archived_text = archived_text.replace(
        "---\n\n", f"archive_reason: {json.dumps(args.reason.strip(), ensure_ascii=False)}\n---\n\n", 1
    )
    target.write_text(archived_text, encoding="utf-8", newline="\n")
    path.unlink()
    old_relative = path.relative_to(scope).as_posix()
    new_relative = target.relative_to(scope).as_posix()
    question_state = load_questions(scope)
    question_changed = False
    for item in question_state["items"]:
        documents = item.get("documents", [])
        replaced = [new_relative if value == old_relative else value for value in documents]
        if replaced != documents:
            item["documents"] = replaced
            item["updated_at"] = now_utc()
            question_changed = True
    if question_changed:
        question_state["updated_at"] = now_utc()
        atomic_json(scope / "questions" / "state.json", question_state)
        write_question_views(scope, question_state)
        append_question_history(scope, {"at": question_state["updated_at"], "event": "knowledge_archived", "document": old_relative, "new_document": new_relative})
    write_sources_index(scope)
    invalidate_active_route(root, config)
    print(f"Archived canonical knowledge document: {target}")
    return 0


def command_knowledge_validate(args: argparse.Namespace) -> int:
    root = workspace(args)
    config = require_config(root)
    scope = selected_scope(root, config, args)
    documents = knowledge_documents(scope)
    if args.document_id:
        documents = [knowledge_document_path(scope, args.document_id)]
    problems: list[str] = []
    for path in documents:
        problems.extend(f"{path.name}: {problem}" for problem in knowledge_document_problems(config, scope, path))
    if problems:
        raise UserError("Knowledge validation failed:\n- " + "\n- ".join(problems))
    print(f"Validated {len(documents)} canonical knowledge document(s) for {scope.name}.")
    return 0


def engine_root_from_config(config: dict[str, Any]) -> Path:
    value = str(nested(config, "engine", "source_root", default="")).strip()
    if not value:
        raise UserError("engine.source_root must be configured before accessing Unreal source")
    root = Path(value).expanduser().resolve()
    if not root.is_dir():
        raise UserError(f"engine.source_root is not accessible: {root}")
    return root


def submodule_scope_paths(config: dict[str, Any], submodule: Path) -> tuple[Path, Path, set[Path]]:
    engine_root = engine_root_from_config(config)
    manifest = load_mapping_yaml(submodule / "submodule.yaml")
    build_cs = nested(manifest, "scope", "build_cs", default="")
    allowed_files = nested(manifest, "scope", "allowed_files", default={})
    if not isinstance(build_cs, str) or not build_cs:
        raise UserError(f"No single Build.cs allowlist configured: {submodule}")
    exact: set[Path] = set()
    build_path = source_root_for_build_cs(engine_root, build_cs)
    source_root = build_path.parent
    exact.add(build_path)
    if isinstance(allowed_files, dict):
        for relative in allowed_files.values():
            if not relative:
                continue
            candidate = (engine_root / str(relative).replace("\\", "/")).resolve()
            try:
                candidate.relative_to(engine_root)
            except ValueError as exc:
                raise UserError(f"Allowed file escapes engine.source_root: {relative}") from exc
            exact.add(candidate)
    return engine_root, source_root, exact


def active_route_path(root: Path, config: dict[str, Any]) -> Path:
    return resolve_inside(root, nested(config, "paths", "active_route_state"), "paths.active_route_state")


def invalidate_active_route(root: Path, config: dict[str, Any]) -> None:
    path = active_route_path(root, config)
    if path.exists():
        path.unlink()


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ensure_active_route(root: Path, config: dict[str, Any], module: Path, submodule: Path) -> dict[str, Any]:
    path = active_route_path(root, config)
    try:
        state = load_json(path)
    except UserError as exc:
        raise UserError(
            "No active route exists. Run `route activate <domain> <submodule> --intent ... --topic ...` before source access."
        ) from exc
    if state.get("domain_id") != module.name or state.get("submodule_id") != submodule.name:
        raise UserError(
            "The requested scope is not active. Activate the requested domain/submodule route first; "
            "this prevents stale context from reaching source commands."
        )
    if state.get("engine_version") != str(nested(config, "engine", "version")):
        raise UserError("Active route engine version is stale; activate a new route")
    if state.get("intent") not in ROUTE_INTENTS or not state.get("topic"):
        raise UserError("Active route is invalid; activate a new route")
    for value in state.get("read_indexes", []):
        candidate = (root / value).resolve()
        if not (candidate.is_relative_to(module.resolve()) or candidate.is_relative_to(submodule.resolve())):
            raise UserError(f"Active route index is outside the active domain/submodule: {value}")
        if not candidate.is_file():
            raise UserError(f"Active route references a missing index: {value}")
    for value in state.get("canonical_documents", []):
        candidate = (root / value).resolve()
        try:
            candidate.relative_to((submodule / "references" / "knowledge").resolve())
        except ValueError as exc:
            raise UserError(f"Active route canonical document is outside the active submodule: {value}") from exc
        if not candidate.is_file():
            raise UserError(f"Active route references a missing canonical document: {value}")
    source_index = submodule / "references" / "indexes" / "sources.index.md"
    if state.get("sources_index_digest") and source_index.is_file() and state["sources_index_digest"] != file_digest(source_index):
        raise UserError("Active route sources index is stale; activate a new route")
    return state


def is_allowed_source_path(engine_root: Path, source_root: Path, exact: set[Path], relative: str) -> Path:
    candidate = (engine_root / relative.replace("\\", "/")).resolve()
    try:
        candidate.relative_to(engine_root)
    except ValueError as exc:
        raise UserError(f"Source path escapes engine.source_root: {relative}") from exc
    if candidate in exact or candidate == source_root or source_root in candidate.parents:
        return candidate
    raise UserError(f"Source path is outside the active submodule allowlist: {relative}")


def command_source_check(args: argparse.Namespace) -> int:
    root = workspace(args)
    config = require_config(root)
    module = require_module(root, config, args.module)
    submodule = require_versioned_submodule(config, module, args.submodule)
    ensure_active_route(root, config, module, submodule)
    engine_root, source_root, exact = submodule_scope_paths(config, submodule)
    candidate = is_allowed_source_path(engine_root, source_root, exact, args.path)
    if not candidate.exists():
        raise UserError(f"Allowed source path does not exist: {args.path}")
    print(f"allowed\t{candidate}")
    return 0


def command_source_read(args: argparse.Namespace) -> int:
    root = workspace(args)
    config = require_config(root)
    module = require_module(root, config, args.module)
    submodule = require_versioned_submodule(config, module, args.submodule)
    ensure_active_route(root, config, module, submodule)
    engine_root, source_root, exact = submodule_scope_paths(config, submodule)
    candidate = is_allowed_source_path(engine_root, source_root, exact, args.path)
    if not candidate.is_file():
        raise UserError(f"Allowed source path is not a file: {args.path}")
    lines = candidate.read_text(encoding="utf-8", errors="replace").splitlines()
    start = max(args.start, 1)
    end = min(args.end, len(lines)) if args.end else len(lines)
    for number in range(start, end + 1):
        print(f"{number}: {lines[number - 1]}")
    return 0


def command_source_search(args: argparse.Namespace) -> int:
    root = workspace(args)
    config = require_config(root)
    module = require_module(root, config, args.module)
    submodule = require_versioned_submodule(config, module, args.submodule)
    ensure_active_route(root, config, module, submodule)
    engine_root, source_root, exact = submodule_scope_paths(config, submodule)
    try:
        pattern = re.compile(args.pattern, re.IGNORECASE if args.ignore_case else 0)
    except re.error as exc:
        raise UserError(f"Invalid search regex: {exc}") from exc
    candidates: set[Path] = set(exact)
    if source_root.is_dir():
        candidates.update(path for path in source_root.rglob("*") if path.is_file())
    hits = 0
    for candidate in sorted(candidates):
        if not candidate.is_file():
            continue
        if candidate.suffix.lower() not in {".h", ".hpp", ".cpp", ".inl", ".cs", ".uplugin", ".ini", ".md", ".txt"}:
            continue
        for number, line in enumerate(candidate.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            if pattern.search(line):
                print(f"{candidate.relative_to(engine_root).as_posix()}:{number}:{line}")
                hits += 1
                if hits >= args.max_results:
                    return 0
    return 0


def command_module_list(args: argparse.Namespace) -> int:
    root = workspace(args)
    config = require_config(root)
    modules = modules_directory(root, config)
    found = False
    if modules.is_dir():
        for directory in sorted(modules.iterdir()):
            if directory.is_dir() and (directory / "module.yaml").is_file():
                found = True
                manifest = load_mapping_yaml(directory / "module.yaml")
                print(f"{directory.name}\t{nested(manifest, 'module', 'name')}\t{nested(manifest, 'module', 'status')}")
    if not found:
        print("No learning modules have been created.")
    return 0


def command_module_rebuild_index(args: argparse.Namespace) -> int:
    root = workspace(args)
    config = require_config(root)
    write_modules_index(root, config)
    print("Rebuilt modules/index.md.")
    return 0


def load_initialization(module: Path) -> dict[str, Any]:
    return load_json(module / "initialization" / "state.json")


def append_initialization_history(module: Path, event: dict[str, Any]) -> None:
    with (module / "initialization" / "history.jsonl").open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def command_module_status(args: argparse.Namespace) -> int:
    root = workspace(args)
    config = require_config(root)
    module = require_module(root, config, args.module)
    ensure_scope_engine_version(config, module)
    state = load_initialization(module)
    print(f"domain={module.name} initialization_state={state.get('state')}")
    print(f"query={state.get('query') or ''}")
    print(f"discovery_root={state.get('discovery_root') or ''}")
    print(f"candidates={len(state.get('candidates', []))}")
    print(f"confirmed_submodules={', '.join(state.get('confirmed_submodules', []))}")
    return 0


def manifest_engine_version(manifest_path: Path) -> str:
    manifest = load_mapping_yaml(manifest_path)
    return str(nested(manifest, "engine", "version", default="")).strip()


def update_manifest_engine_version(manifest_path: Path, version: str) -> None:
    text = manifest_path.read_text(encoding="utf-8")
    if not re.search(r"(?m)^  version:\s*", text):
        raise UserError(f"Manifest has no engine.version field: {manifest_path}")
    text = re.sub(r"(?m)^  version:\s*.*$", f"  version: {json.dumps(version, ensure_ascii=False)}", text, count=1)
    manifest_path.write_text(text, encoding="utf-8", newline="\n")


def mark_knowledge_stale(scope: Path, old_version: str) -> list[str]:
    changed: list[str] = []
    for path in knowledge_documents(scope):
        text = path.read_text(encoding="utf-8")
        metadata = knowledge_metadata(path)
        if metadata.get("engine_version") == old_version:
            text = replace_frontmatter_value(text, "evidence_status", "stale_version")
            path.write_text(text, encoding="utf-8", newline="\n")
            changed.append(path.name)
    return changed


def command_version_status(args: argparse.Namespace) -> int:
    root = workspace(args)
    config = require_config(root)
    module = require_module(root, config, args.module)
    configured = str(nested(config, "engine", "version"))
    print(f"configured_engine_version={configured}")
    print(f"domain_manifest_version={manifest_engine_version(module / 'module.yaml')}")
    directory = submodules_directory(module)
    if directory.is_dir():
        for item in sorted(directory.iterdir()):
            if item.is_dir() and (item / "submodule.yaml").is_file():
                print(f"submodule={item.name}\tversion={manifest_engine_version(item / 'submodule.yaml')}")
    return 0


def command_version_migrate(args: argparse.Namespace) -> int:
    root = workspace(args)
    config = require_config(root)
    module = require_module(root, config, args.module)
    configured = str(nested(config, "engine", "version"))
    reason = args.reason.strip()
    if not reason:
        raise UserError("Version migration requires a non-empty --reason")
    manifests = [module / "module.yaml"]
    directory = submodules_directory(module)
    if args.submodule:
        submodule = require_submodule(module, args.submodule)
        manifests.append(submodule / "submodule.yaml")
    elif directory.is_dir():
        manifests.extend(
            item / "submodule.yaml"
            for item in sorted(directory.iterdir())
            if item.is_dir() and (item / "submodule.yaml").is_file()
        )
    old_versions = {str(path): manifest_engine_version(path) for path in manifests}
    if all(value == configured for value in old_versions.values()):
        raise UserError(f"All selected manifests already use configured engine version {configured}")
    if args.dry_run:
        print(f"Would migrate {module.name} manifests to engine version {configured}")
        for path, version in old_versions.items():
            print(f"  {path}: {version} -> {configured}")
        return 0
    timestamp = now_utc()
    for manifest_path in manifests:
        update_manifest_engine_version(manifest_path, configured)
    stale_documents: dict[str, list[str]] = {}
    scopes = [module]
    if not args.submodule and directory.is_dir():
        scopes.extend(item for item in directory.iterdir() if item.is_dir() and (item / "submodule.yaml").is_file())
    elif args.submodule:
        scopes.append(require_submodule(module, args.submodule))
    for scope in scopes:
        manifest_path = scope / ("module.yaml" if scope == module else "submodule.yaml")
        stale_documents[scope.name] = mark_knowledge_stale(scope, old_versions.get(str(manifest_path), ""))
        write_sources_index(scope)
        if (scope / "process" / "history.jsonl").is_file():
            append_history(scope, {
                "at": timestamp,
                "event": "engine_version_migrated",
                "from": old_versions.get(str(manifest_path), "unknown"),
                "to": configured,
                "reason": reason,
                "stale_documents": stale_documents[scope.name],
            })
    active = active_route_path(root, config)
    if active.exists():
        active.unlink()
    write_modules_index(root, config)
    print(f"Migrated {module.name} to engine version {configured}; stale knowledge was marked explicitly.")
    return 0


def normalize_engine_relative(value: str) -> str:
    normalized = value.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def candidate_module_name(path: str) -> str:
    filename = Path(path).name
    if filename.endswith(".Build.cs"):
        return filename[: -len(".Build.cs")]
    if filename.endswith(".uplugin"):
        return filename[: -len(".uplugin")]
    return Path(filename).stem


def discover_build_cs(engine_root: Path, query: str, within: str | None) -> tuple[str, list[dict[str, Any]]]:
    relative_root = normalize_engine_relative(within or ".")
    search_root = resolve_inside(engine_root, relative_root, "discovery root")
    if not search_root.is_dir():
        raise UserError(f"Discovery root is not a directory: {within}")
    normalized_query = query.strip().casefold()
    compact_query = re.sub(r"[^a-z0-9]+", "", normalized_query)
    if not normalized_query:
        raise UserError("Discovery query cannot be empty")
    files = [path for path in sorted(search_root.rglob("*")) if path.is_file()]
    plugin_files = [path for path in files if path.suffix.lower() == ".uplugin"]
    build_files = [path for path in files if path.name.endswith(".Build.cs")]
    plugins_by_directory = {path.parent.resolve(): path for path in plugin_files}
    groups: dict[str, dict[str, Any]] = {}

    def plugin_for(build_path: Path) -> Path | None:
        current = build_path.parent.resolve()
        engine_resolved = engine_root.resolve()
        while current == engine_resolved or engine_resolved in current.parents:
            if current in plugins_by_directory:
                return plugins_by_directory[current]
            if current == engine_resolved:
                break
            current = current.parent
        return None

    for build_path in build_files:
        build_relative = build_path.relative_to(engine_root).as_posix()
        plugin_path = plugin_for(build_path)
        if plugin_path:
            group_key = plugin_path.resolve().as_posix()
            domain_name = candidate_module_name(plugin_path.relative_to(engine_root).as_posix())
            domain_path = plugin_path.relative_to(engine_root).as_posix()
        else:
            group_key = build_path.parent.resolve().as_posix()
            domain_name = build_path.parent.name
            domain_path = build_path.parent.relative_to(engine_root).as_posix()
        haystack = " ".join((domain_name, domain_path, build_relative)).casefold()
        compact_haystack = re.sub(r"[^a-z0-9]+", "", haystack)
        if normalized_query not in haystack and (not compact_query or compact_query not in compact_haystack):
            continue
        group = groups.setdefault(group_key, {
            "kind": "domain_candidate",
            "name": domain_name,
            "path": domain_path,
            "plugin_path": plugin_path.relative_to(engine_root).as_posix() if plugin_path else None,
            "build_cs": [],
        })
        group["build_cs"].append({
            "name": candidate_module_name(build_relative),
            "path": build_relative,
        })

    # A matching plugin name should surface its Build.cs group even when the Build.cs filename does not contain the query.
    for plugin_path in plugin_files:
        plugin_relative = plugin_path.relative_to(engine_root).as_posix()
        plugin_name = candidate_module_name(plugin_relative)
        plugin_haystack = (plugin_name + " " + plugin_relative).casefold()
        plugin_compact = re.sub(r"[^a-z0-9]+", "", plugin_haystack)
        if normalized_query not in plugin_haystack and (not compact_query or compact_query not in plugin_compact):
            continue
        key = plugin_path.resolve().as_posix()
        if key in groups:
            continue
        group = {
            "kind": "domain_candidate",
            "name": plugin_name,
            "path": plugin_relative,
            "plugin_path": plugin_relative,
            "build_cs": [],
        }
        for build_path in build_files:
            if plugin_path.parent.resolve() in build_path.resolve().parents:
                relative = build_path.relative_to(engine_root).as_posix()
                group["build_cs"].append({"name": candidate_module_name(relative), "path": relative})
        groups[key] = group
    return relative_root, list(groups.values())


def command_discover_build_cs(args: argparse.Namespace) -> int:
    root = workspace(args)
    config = require_config(root)
    engine_root = engine_root_from_config(config)
    relative_root, candidates = discover_build_cs(engine_root, args.query, args.within)
    discovery = {
        "schema_version": 1,
        "query": args.query,
        "discovery_root": relative_root,
        "discovery_mode": "metadata_only",
        "candidates": candidates,
        "updated_at": now_utc(),
    }
    discovery_path = resolve_inside(root, nested(config, "paths", "discovery_state"), "paths.discovery_state")
    atomic_json(discovery_path, discovery)
    if args.module:
        module = require_module(root, config, args.module)
        ensure_domain_engine_version(config, module)
        state = load_initialization(module)
        timestamp = now_utc()
        state.update({
            "state": "candidate_confirmation_required",
            "query": args.query,
            "discovery_root": relative_root,
            "discovery_mode": "metadata_only",
            "candidates": candidates,
            "updated_at": timestamp,
        })
        atomic_json(module / "initialization" / "state.json", state)
        append_initialization_history(module, {
            "at": timestamp,
            "event": "discovery_completed",
            "query": args.query,
            "discovery_root": relative_root,
            "candidate_count": len(candidates),
        })
    print(
        "Metadata-only discovery completed "
        f"(root={relative_root}; no separate authorization required; no .h/.cpp content was read)."
    )
    if not candidates:
        print("No metadata candidates found.")
        return 0
    print("Metadata-only domain candidates:")
    for index, candidate in enumerate(candidates, start=1):
        print(f"{index}. {candidate['name']}\t{candidate['path']}")
        for build_cs in candidate.get("build_cs", []):
            print(f"   - {build_cs['name']}.Build.cs\t{build_cs['path']}")
    if args.module:
        print(f"Candidates recorded for {args.module}; confirm selected Build.cs paths with module confirm.")
    return 0


def command_module_confirm(args: argparse.Namespace) -> int:
    root = workspace(args)
    config = require_config(root)
    module = require_module(root, config, args.module)
    ensure_domain_engine_version(config, module)
    state = load_initialization(module)
    requested = [normalize_engine_relative(value) for value in args.build_cs if value.strip()]
    if not requested:
        raise UserError("At least one --build-cs is required for confirmation")
    candidates = {
        build.get("path")
        for item in state.get("candidates", [])
        for build in item.get("build_cs", [])
        if isinstance(build, dict) and build.get("path")
    }
    if candidates:
        unknown = [value for value in requested if value not in candidates]
        if unknown:
            raise UserError("Build.cs paths were not in the recorded discovery candidates: " + ", ".join(unknown))
    existing = set(state.get("confirmed_build_cs", []))
    if existing.intersection(requested):
        raise UserError("Build.cs already confirmed: " + ", ".join(sorted(existing.intersection(requested))))
    submodule_ids: list[str] = []
    for build_cs in requested:
        display_name = candidate_module_name(build_cs)
        submodule_id = slugify(display_name)
        command_submodule_create(argparse.Namespace(
            root=args.root,
            module=module.name,
            name=display_name,
            id=submodule_id,
            build_cs=build_cs,
            allow_file=[],
            dry_run=False,
            register_initialization=False,
        ))
        submodule_ids.append(submodule_id)
    timestamp = now_utc()
    state["state"] = "ready_for_learning"
    state["confirmed_build_cs"] = list(state.get("confirmed_build_cs", [])) + requested
    state["confirmed_submodules"] = list(state.get("confirmed_submodules", [])) + submodule_ids
    state["updated_at"] = timestamp
    atomic_json(module / "initialization" / "state.json", state)
    append_initialization_history(module, {
        "at": timestamp,
        "event": "submodules_registered",
        "build_cs": requested,
        "submodules": submodule_ids,
    })
    print(f"Confirmed and registered submodules: {', '.join(submodule_ids)}")
    return 0


def command_process_show(args: argparse.Namespace) -> int:
    root = workspace(args)
    config = require_config(root)
    module = selected_scope(root, config, args)
    state = load_process(module)
    print(f"scope={module.name} status={state['status']} current_stage={state['current_stage']}")
    for stage in STAGES:
        item = state["stages"][stage]
        print(f"  {stage}: {item['status']}")
    return 0


def command_process_start(args: argparse.Namespace) -> int:
    root = workspace(args)
    config = require_config(root)
    module = selected_scope(root, config, args)
    state = load_process(module)
    stage = state["current_stage"]
    current = state["stages"][stage]
    if current["status"] == "completed":
        raise UserError(f"Current stage is already completed: {stage}")
    if current["status"] == "in_progress":
        raise UserError(f"Current stage is already in progress: {stage}")
    timestamp = now_utc()
    event_type = "process_started" if state["status"] == "not_started" else "stage_resumed"
    current["status"] = "in_progress"
    current["started_at"] = current.get("started_at") or timestamp
    state["status"] = "in_progress"
    state["updated_at"] = timestamp
    atomic_json(module / "process" / "state.json", state)
    append_history(module, {"at": timestamp, "event": event_type, "stage": stage, "reason": args.reason or ""})
    print(f"Started {module.name} process stage: {stage}")
    return 0


def command_process_advance(args: argparse.Namespace) -> int:
    root = workspace(args)
    config = require_config(root)
    module = selected_scope(root, config, args)
    state = load_process(module)
    stage = state["current_stage"]
    current = state["stages"][stage]
    summary = args.summary.strip()
    evidence = [item.strip() for item in args.evidence if item.strip()]
    work_completed = args.work_completed.strip()
    exit_assessment = args.exit_assessment.strip()
    next_handoff = args.next_handoff.strip()
    deliverables = sorted({value.strip() for value in args.deliverable if value.strip()})
    if current["status"] != "in_progress":
        raise UserError(f"Stage {stage} must be in_progress before advancing")
    if not summary or not evidence or not work_completed or not exit_assessment or not next_handoff or not deliverables:
        raise UserError(
            "Advancing requires --summary, --work-completed, --exit-assessment, --next-handoff, "
            "at least one --deliverable, and at least one --evidence"
        )
    timestamp = now_utc()
    current.update({
        "status": "completed",
        "completed_at": timestamp,
        "summary": summary,
        "evidence": evidence,
        "work_completed": work_completed,
        "exit_assessment": exit_assessment,
        "next_stage_handoff": next_handoff,
        "deliverables": deliverables,
    })
    problems = stage_exit_problems(module, stage, state)
    if problems:
        raise UserError("Cannot complete stage:\n- " + "\n- ".join(problems))
    index = STAGES.index(stage)
    next_stage = STAGES[index + 1] if index + 1 < len(STAGES) else None
    if next_stage:
        state["current_stage"] = next_stage
        state["stages"][next_stage]["status"] = "in_progress"
        state["stages"][next_stage]["started_at"] = timestamp
        state["status"] = "in_progress"
    else:
        state["status"] = "completed"
    state["updated_at"] = timestamp
    atomic_json(module / "process" / "state.json", state)
    record_stage_transition(
        module, stage, summary, evidence, work_completed, exit_assessment, next_handoff, deliverables, timestamp
    )
    append_history(
        module,
        {
            "at": timestamp,
            "event": "stage_completed",
            "stage": stage,
            "next_stage": next_stage,
            "summary": summary,
            "work_completed": work_completed,
            "exit_assessment": exit_assessment,
            "next_stage_handoff": next_handoff,
            "deliverables": deliverables,
            "evidence": evidence,
        },
    )
    print(f"Completed stage {stage}." + (f" Started {next_stage}." if next_stage else " Module process completed."))
    return 0


def command_process_block(args: argparse.Namespace) -> int:
    root = workspace(args)
    config = require_config(root)
    module = selected_scope(root, config, args)
    state = load_process(module)
    stage = state["current_stage"]
    if state["stages"][stage]["status"] != "in_progress":
        raise UserError(f"Stage {stage} must be in_progress before it can be blocked")
    reason = args.reason.strip()
    if not reason:
        raise UserError("Blocking a stage requires a non-empty --reason")
    timestamp = now_utc()
    state["stages"][stage]["status"] = "blocked"
    state["status"] = "blocked"
    state["updated_at"] = timestamp
    atomic_json(module / "process" / "state.json", state)
    append_history(module, {"at": timestamp, "event": "stage_blocked", "stage": stage, "reason": reason})
    print(f"Blocked {module.name} process stage {stage}: {reason}")
    return 0


def command_question_add(args: argparse.Namespace) -> int:
    root = workspace(args)
    config = require_config(root)
    module = selected_scope(root, config, args)
    question = " ".join(args.text.split())
    why = args.why.strip()
    if not question or not why:
        raise UserError("Question text and --why must be non-empty")
    state = load_questions(module)
    normalized = question.casefold().rstrip("?？。 ")
    for item in state["items"]:
        if item["question"].casefold().rstrip("?？。 ") == normalized:
            raise UserError(f"Duplicate cached question: {item['id']}")
    process = load_process(module)
    stage = args.stage or process["current_stage"]
    if stage not in STAGES:
        raise UserError(f"Invalid discovery stage: {stage}")
    number = int(state.get("next_id", 1))
    question_id = f"Q-{number:04d}"
    timestamp = now_utc()
    item = {
        "id": question_id,
        "status": "open",
        "priority": args.priority,
        "topic": args.topic.strip() or "general",
        "stage": stage,
        "question": question,
        "why": why,
        "answer": "",
        "evidence": [],
        "documents": [],
        "promoted_from": "",
        "promoted_to": [],
        "domain_resolution_status": "",
        "status_note": "",
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    state["items"].append(item)
    state["next_id"] = number + 1
    state["updated_at"] = timestamp
    atomic_json(module / "questions" / "state.json", state)
    write_question_views(module, state)
    append_question_history(module, {"at": timestamp, "event": "question_added", "question": question_id})
    print(f"Cached question {question_id} in stage {stage}.")
    return 0


def command_question_list(args: argparse.Namespace) -> int:
    root = workspace(args)
    config = require_config(root)
    module = selected_scope(root, config, args)
    state = load_questions(module)
    items = [item for item in state["items"] if not args.status or item["status"] == args.status]
    if not items:
        print("No matching cached questions.")
        return 0
    for item in items:
        print(f"{item['id']}\t{item['status']}\t{item['priority']}\t{item['stage']}\t{item['question']}")
    return 0


def command_question_status(args: argparse.Namespace) -> int:
    root = workspace(args)
    config = require_config(root)
    module = selected_scope(root, config, args)
    state = load_questions(module)
    item = find_question(state, args.question_id)
    target = args.status
    allowed = {
        "open": {"investigating", "archived"},
        "investigating": {"open", "answered", "archived"},
        "answered": {"investigating", "verified", "archived"},
        "verified": {"investigating", "archived"},
        "archived": {"open"},
    }
    if target not in allowed[item["status"]]:
        raise UserError(f"Invalid question transition: {item['status']} -> {target}")
    if target in ("answered", "verified") and (not item.get("answer") or not item.get("evidence")):
        raise UserError(f"{target} requires an answer and evidence; use question answer first")
    if target == "verified" and not item.get("documents"):
        raise UserError("verified requires at least one linked canonical document")
    item["status"] = target
    item["status_note"] = args.reason.strip() if args.reason else ""
    item["updated_at"] = now_utc()
    state["updated_at"] = item["updated_at"]
    atomic_json(module / "questions" / "state.json", state)
    write_question_views(module, state)
    append_question_history(module, {"at": item["updated_at"], "event": "question_status_changed", "question": item["id"], "status": target})
    print(f"Updated {item['id']} status to {target}.")
    return 0


def command_question_answer(args: argparse.Namespace) -> int:
    root = workspace(args)
    config = require_config(root)
    module = selected_scope(root, config, args)
    state = load_questions(module)
    item = find_question(state, args.question_id)
    answer = args.answer.strip()
    evidence = [value.strip() for value in args.evidence if value.strip()]
    documents = [validate_knowledge_document_path(module, value) for value in args.document if value.strip()]
    if not answer or not evidence:
        raise UserError("Answering requires non-empty --answer and at least one --evidence")
    if args.verified and not documents and not item.get("documents"):
        raise UserError("--verified requires at least one --document")
    timestamp = now_utc()
    item["answer"] = answer
    item["evidence"] = evidence
    item["documents"] = documents or item.get("documents", [])
    item["status"] = "verified" if args.verified else "answered"
    item["status_note"] = ""
    item["updated_at"] = timestamp
    state["updated_at"] = timestamp
    atomic_json(module / "questions" / "state.json", state)
    write_question_views(module, state)
    link_question_to_documents(module, item["id"], item["documents"])
    invalidate_active_route(root, config)
    append_question_history(module, {"at": timestamp, "event": "question_answered", "question": item["id"], "status": item["status"], "documents": item["documents"]})
    if item.get("promoted_from"):
        promoted_from = item.get("promoted_from", "")
        if promoted_from and ":" in promoted_from:
            source_id, source_question_id = promoted_from.split(":", 1)
            source = require_submodule(require_module(root, config, args.module), source_id)
            source_state = load_questions(source)
            source_item = find_question(source_state, source_question_id)
            source_item["domain_resolution_status"] = item["status"]
            source_item["updated_at"] = timestamp
            source_state["updated_at"] = timestamp
            atomic_json(source / "questions" / "state.json", source_state)
            write_question_views(source, source_state)
            append_question_history(source, {"at": timestamp, "event": "domain_question_resolved", "question": source_question_id, "domain_question": item["id"], "status": item["status"]})
    print(f"Recorded {item['status']} answer for {item['id']}.")
    return 0


def command_question_rebuild(args: argparse.Namespace) -> int:
    root = workspace(args)
    config = require_config(root)
    module = selected_scope(root, config, args)
    state = load_questions(module)
    write_question_views(module, state)
    print(f"Rebuilt question views for {module.name}.")
    return 0


def command_question_promote(args: argparse.Namespace) -> int:
    root = workspace(args)
    config = require_config(root)
    domain = require_module(root, config, args.module)
    ensure_scope_engine_version(config, domain)
    source_submodule = require_submodule(domain, args.from_submodule)
    ensure_scope_engine_version(config, source_submodule)
    source_state = load_questions(source_submodule)
    source_item = find_question(source_state, args.question_id)
    target_state = load_questions(domain)
    source_ref = f"{source_submodule.name}:{source_item['id']}"
    if any(item.get("promoted_from") == source_ref for item in target_state["items"]):
        raise UserError(f"Question already promoted: {source_ref}")
    number = int(target_state.get("next_id", 1))
    timestamp = now_utc()
    promoted = dict(source_item)
    promoted.update({
        "id": f"Q-{number:04d}",
        "status": "answered" if source_item.get("answer") and source_item.get("evidence") else "open",
        "documents": [],
        "promoted_from": source_ref,
        "promoted_to": [],
        "promotion_reason": args.reason.strip(),
        "status_note": args.reason.strip(),
        "created_at": timestamp,
        "updated_at": timestamp,
    })
    target_state["items"].append(promoted)
    target_state["next_id"] = number + 1
    target_state["updated_at"] = timestamp
    source_item.setdefault("promoted_to", []).append(f"{domain.name}:{promoted['id']}")
    source_item["updated_at"] = timestamp
    source_state["updated_at"] = timestamp
    atomic_json(source_submodule / "questions" / "state.json", source_state)
    write_question_views(source_submodule, source_state)
    atomic_json(domain / "questions" / "state.json", target_state)
    write_question_views(domain, target_state)
    append_question_history(source_submodule, {"at": timestamp, "event": "question_promoted", "question": source_item["id"], "domain_question": promoted["id"], "reason": args.reason.strip()})
    append_question_history(domain, {"at": timestamp, "event": "question_promoted_in", "question": promoted["id"], "source": source_ref, "reason": args.reason.strip()})
    print(f"Promoted {source_ref} to domain question {promoted['id']}.")
    return 0


def route_role_for_intent(intent: str) -> str:
    return {
        "orient": "source-mapper",
        "explain": "source-mapper",
        "trace": "callflow-tracer",
        "extend": "callflow-tracer",
        "diagnose": "boundary-guard",
        "compare_version": "source-mapper",
        "review": "question-curator",
    }[intent]


def markdown_index_terms(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    terms: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = [cell.strip().strip("`").casefold() for cell in line.strip("|").split("|")]
        if cells and cells[0] and cells[0] not in {"id", "topic", "intent", "constraint", "prompt"}:
            terms.add(cells[0])
    return terms


def command_route_activate(args: argparse.Namespace) -> int:
    root = workspace(args)
    config = require_config(root)
    module = require_module(root, config, args.module)
    ensure_domain_engine_version(config, module)
    initialization = load_initialization(module)
    if initialization.get("state") != "ready_for_learning":
        raise UserError(
            f"Domain {module.name} is not ready for learning (state={initialization.get('state')}); confirm Build.cs submodules first"
        )
    submodule = require_versioned_submodule(config, module, args.submodule)
    intent = args.intent
    topic = " ".join(args.topic.split())
    if intent not in ROUTE_INTENTS or not topic:
        raise UserError("Route activation requires a supported --intent and non-empty --topic")
    budget = int(nested(config, "routing", "max_canonical_docs", default=3))
    documents = []
    for path in knowledge_documents(submodule):
        metadata = knowledge_metadata(path)
        haystack = " ".join(metadata.get(key, "") for key in ("id", "title", "topic")).casefold()
        if topic.casefold() in haystack:
            documents.append(path)
    if not documents:
        documents = knowledge_documents(submodule)
    documents = documents[:budget]
    topic_terms = markdown_index_terms(submodule / "references" / "indexes" / "topics.index.md")
    constraint_terms = markdown_index_terms(submodule / "references" / "indexes" / "constraints.index.md")
    route_constraints = [value.strip() for value in args.constraint if value.strip()]
    index_files = [
        (module / "ROUTER.md").relative_to(root).as_posix(),
        (module / "submodules" / "index.md").relative_to(root).as_posix(),
        (module / "references" / "indexes" / "routing.index.md").relative_to(root).as_posix(),
        (module / "references" / "indexes" / "intents.index.md").relative_to(root).as_posix(),
        (module / "references" / "indexes" / "topics.index.md").relative_to(root).as_posix(),
        (module / "references" / "indexes" / "constraints.index.md").relative_to(root).as_posix(),
        (module / "questions" / "index.md").relative_to(root).as_posix(),
        (submodule / "ROUTER.md").relative_to(root).as_posix(),
        (submodule / "references" / "indexes" / "routing.index.md").relative_to(root).as_posix(),
        (submodule / "references" / "indexes" / "intents.index.md").relative_to(root).as_posix(),
        (submodule / "references" / "indexes" / "topics.index.md").relative_to(root).as_posix(),
        (submodule / "references" / "indexes" / "constraints.index.md").relative_to(root).as_posix(),
        (submodule / "questions" / "index.md").relative_to(root).as_posix(),
    ]
    missing_indexes = [value for value in index_files if not (root / value).is_file()]
    if missing_indexes:
        raise UserError("Cannot activate route; missing indexes:\n- " + "\n- ".join(missing_indexes))
    route = {
        "schema_version": 1,
        "generation": str(uuid.uuid4()),
        "activated_at": now_utc(),
        "domain_id": module.name,
        "submodule_id": submodule.name,
        "engine_version": str(nested(config, "engine", "version")),
        "intent": intent,
        "topic": topic,
        "anchor": args.anchor or "",
        "constraints": route_constraints,
        "role": route_role_for_intent(intent),
        "read_indexes": index_files,
        "canonical_documents": [path.relative_to(root).as_posix() for path in documents],
        "topic_match": "indexed" if topic.casefold() in topic_terms else "document_metadata",
        "constraint_matches": [value for value in route_constraints if value.casefold() in constraint_terms],
        "sources_index_digest": file_digest(submodule / "references" / "indexes" / "sources.index.md"),
        "context_reset_required": True,
    }
    path = active_route_path(root, config)
    atomic_json(path, route)
    print(f"Activated route generation={route['generation']}")
    print(f"domain={module.name} submodule={submodule.name} intent={intent} topic={topic}")
    print(f"role={route['role']} canonical_documents={len(documents)}")
    for value in route["read_indexes"]:
        print(f"index={value}")
    for value in route["canonical_documents"]:
        print(f"document={value}")
    return 0


def command_route_show(args: argparse.Namespace) -> int:
    root = workspace(args)
    config = require_config(root)
    path = active_route_path(root, config)
    state = load_json(path)
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


def command_route_clear(args: argparse.Namespace) -> int:
    root = workspace(args)
    config = require_config(root)
    path = active_route_path(root, config)
    if path.exists():
        path.unlink()
    print("Cleared active route.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage the UE Source Sage learning framework")
    parser.add_argument("--root", help="Workspace root; defaults to the repository containing this skill")
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="Validate config, indexes, knowledge, process, questions, and engine versions")
    validate.set_defaults(handler=command_validate)
    preflight = commands.add_parser("preflight", help="Validate global config before unlocking workflows")
    preflight.set_defaults(handler=command_preflight)

    version = commands.add_parser("version", help="Inspect or migrate scope engine-version metadata")
    version_commands = version.add_subparsers(dest="version_command", required=True)
    version_status = version_commands.add_parser("status")
    version_status.add_argument("module")
    version_status.set_defaults(handler=command_version_status)
    version_migrate = version_commands.add_parser("migrate")
    version_migrate.add_argument("module")
    version_migrate.add_argument("--submodule")
    version_migrate.add_argument("--reason", required=True)
    version_migrate.add_argument("--dry-run", action="store_true")
    version_migrate.set_defaults(handler=command_version_migrate)

    route = commands.add_parser("route", help="Resolve and activate one executable domain/submodule route")
    route_commands = route.add_subparsers(dest="route_command", required=True)
    activate_route = route_commands.add_parser("activate")
    activate_route.add_argument("module")
    activate_route.add_argument("submodule")
    activate_route.add_argument("--intent", required=True, choices=ROUTE_INTENTS)
    activate_route.add_argument("--topic", required=True)
    activate_route.add_argument("--anchor")
    activate_route.add_argument("--constraint", action="append", default=[])
    activate_route.set_defaults(handler=command_route_activate)
    resolve_route = route_commands.add_parser("resolve")
    resolve_route.add_argument("module")
    resolve_route.add_argument("submodule")
    resolve_route.add_argument("--intent", required=True, choices=ROUTE_INTENTS)
    resolve_route.add_argument("--topic", required=True)
    resolve_route.add_argument("--anchor")
    resolve_route.add_argument("--constraint", action="append", default=[])
    resolve_route.set_defaults(handler=command_route_activate)
    show_route = route_commands.add_parser("show")
    show_route.set_defaults(handler=command_route_show)
    clear_route = route_commands.add_parser("clear")
    clear_route.set_defaults(handler=command_route_clear)

    module = commands.add_parser("module", help="Manage isolated source-learning modules")
    module_commands = module.add_subparsers(dest="module_command", required=True)
    create = module_commands.add_parser("create", help="Create an empty module framework")
    create.add_argument("name")
    create.add_argument("--id")
    create.add_argument("--from-discovery", action="store_true", help="Attach the latest metadata-only discovery result")
    create.add_argument("--dry-run", action="store_true")
    create.set_defaults(handler=command_module_create)
    list_modules = module_commands.add_parser("list", help="List configured modules")
    list_modules.set_defaults(handler=command_module_list)
    rebuild_modules = module_commands.add_parser("rebuild-index", help="Regenerate modules/index.md")
    rebuild_modules.set_defaults(handler=command_module_rebuild_index)
    module_status = module_commands.add_parser("status", help="Show domain initialization state")
    module_status.add_argument("module")
    module_status.set_defaults(handler=command_module_status)
    confirm_module = module_commands.add_parser("confirm", help="Confirm Build.cs candidates and register submodules")
    confirm_module.add_argument("module")
    confirm_module.add_argument("--build-cs", required=True, action="append")
    confirm_module.set_defaults(handler=command_module_confirm)

    discover = commands.add_parser("discover", help="Metadata-only discovery within the configured engine source root")
    discover_commands = discover.add_subparsers(dest="discover_command", required=True)
    discover_build = discover_commands.add_parser("build-cs", help="Find matching Build.cs and uplugin names")
    discover_build.add_argument("query")
    discover_build.add_argument("--within", help="Optional engine-relative discovery root; defaults to engine.source_root")
    discover_build.add_argument("--module", help="Record candidates in an existing domain")
    discover_build.set_defaults(handler=command_discover_build_cs)

    submodule = commands.add_parser("submodule", help="Manage Build.cs-scoped submodules")
    submodule_commands = submodule.add_subparsers(dest="submodule_command", required=True)
    create_submodule = submodule_commands.add_parser("create", help="Create a Build.cs-scoped submodule")
    create_submodule.add_argument("module")
    create_submodule.add_argument("name")
    create_submodule.add_argument("--id")
    create_submodule.add_argument("--build-cs", required=True)
    create_submodule.add_argument("--allow-file", action="append", default=[])
    create_submodule.add_argument("--dry-run", action="store_true")
    create_submodule.set_defaults(handler=command_submodule_create)
    list_submodules = submodule_commands.add_parser("list", help="List submodules for a domain")
    list_submodules.add_argument("module")
    list_submodules.set_defaults(handler=command_submodule_list)
    rebuild_submodules = submodule_commands.add_parser("rebuild-index", help="Regenerate a domain submodule index")
    rebuild_submodules.add_argument("module")
    rebuild_submodules.set_defaults(handler=command_submodule_rebuild_index)

    source = commands.add_parser("source", help="Read/search only within the active submodule allowlist")
    source_commands = source.add_subparsers(dest="source_command", required=True)
    check_source = source_commands.add_parser("check")
    check_source.add_argument("module")
    check_source.add_argument("submodule")
    check_source.add_argument("path")
    check_source.set_defaults(handler=command_source_check)
    read_source = source_commands.add_parser("read")
    read_source.add_argument("module")
    read_source.add_argument("submodule")
    read_source.add_argument("path")
    read_source.add_argument("--start", type=int, default=1)
    read_source.add_argument("--end", type=int)
    read_source.set_defaults(handler=command_source_read)
    search_source = source_commands.add_parser("search")
    search_source.add_argument("module")
    search_source.add_argument("submodule")
    search_source.add_argument("pattern")
    search_source.add_argument("--ignore-case", action="store_true")
    search_source.add_argument("--max-results", type=int, default=50)
    search_source.set_defaults(handler=command_source_search)

    process = commands.add_parser("process", help="Manage shared module learning stages")
    process_commands = process.add_subparsers(dest="process_command", required=True)
    show_process = process_commands.add_parser("show")
    show_process.add_argument("module")
    show_process.add_argument("--submodule")
    show_process.set_defaults(handler=command_process_show)
    start_process = process_commands.add_parser("start")
    start_process.add_argument("module")
    start_process.add_argument("--submodule")
    start_process.add_argument("--reason")
    start_process.set_defaults(handler=command_process_start)
    advance_process = process_commands.add_parser("advance")
    advance_process.add_argument("module")
    advance_process.add_argument("--submodule")
    advance_process.add_argument("--summary", required=True)
    advance_process.add_argument("--evidence", required=True, action="append")
    advance_process.add_argument("--work-completed", required=True)
    advance_process.add_argument("--exit-assessment", required=True)
    advance_process.add_argument("--next-handoff", required=True)
    advance_process.add_argument("--deliverable", required=True, action="append")
    advance_process.set_defaults(handler=command_process_advance)
    block_process = process_commands.add_parser("block")
    block_process.add_argument("module")
    block_process.add_argument("--submodule")
    block_process.add_argument("--reason", required=True)
    block_process.set_defaults(handler=command_process_block)

    question = commands.add_parser("question", help="Manage cached module questions")
    question_commands = question.add_subparsers(dest="question_command", required=True)
    add_question = question_commands.add_parser("add")
    add_question.add_argument("module")
    add_question.add_argument("--submodule")
    add_question.add_argument("--text", required=True)
    add_question.add_argument("--why", required=True)
    add_question.add_argument("--topic", default="general")
    add_question.add_argument("--priority", choices=QUESTION_PRIORITIES, default="medium")
    add_question.add_argument("--stage", choices=STAGES)
    add_question.set_defaults(handler=command_question_add)
    list_questions = question_commands.add_parser("list")
    list_questions.add_argument("module")
    list_questions.add_argument("--submodule")
    list_questions.add_argument("--status", choices=QUESTION_STATUSES)
    list_questions.set_defaults(handler=command_question_list)
    status_question = question_commands.add_parser("status")
    status_question.add_argument("module")
    status_question.add_argument("--submodule")
    status_question.add_argument("question_id")
    status_question.add_argument("--status", required=True, choices=QUESTION_STATUSES)
    status_question.add_argument("--reason")
    status_question.set_defaults(handler=command_question_status)
    answer_question = question_commands.add_parser("answer")
    answer_question.add_argument("module")
    answer_question.add_argument("--submodule")
    answer_question.add_argument("question_id")
    answer_question.add_argument("--answer", required=True)
    answer_question.add_argument("--evidence", required=True, action="append")
    answer_question.add_argument("--document", action="append", default=[])
    answer_question.add_argument("--verified", action="store_true")
    answer_question.set_defaults(handler=command_question_answer)
    promote_question = question_commands.add_parser("promote")
    promote_question.add_argument("module")
    promote_question.add_argument("question_id")
    promote_question.add_argument("--from-submodule", required=True)
    promote_question.add_argument("--reason", required=True)
    promote_question.set_defaults(handler=command_question_promote)
    rebuild_questions = question_commands.add_parser("rebuild")
    rebuild_questions.add_argument("module")
    rebuild_questions.add_argument("--submodule")
    rebuild_questions.set_defaults(handler=command_question_rebuild)

    knowledge = commands.add_parser("knowledge", help="Manage canonical learning documents")
    knowledge_commands = knowledge.add_subparsers(dest="knowledge_command", required=True)
    create_knowledge = knowledge_commands.add_parser("create")
    create_knowledge.add_argument("module")
    create_knowledge.add_argument("--submodule")
    create_knowledge.add_argument("--id")
    create_knowledge.add_argument("--title", required=True)
    create_knowledge.add_argument("--topic", default="general")
    create_knowledge.add_argument("--answer", required=True)
    create_knowledge.add_argument("--source", action="append", required=True)
    create_knowledge.add_argument("--question-id", action="append", default=[])
    create_knowledge.add_argument("--evidence-status", choices=KNOWLEDGE_EVIDENCE_STATUSES, default="draft")
    create_knowledge.add_argument("--dry-run", action="store_true")
    create_knowledge.set_defaults(handler=command_knowledge_create)
    rebuild_knowledge = knowledge_commands.add_parser("rebuild-index")
    rebuild_knowledge.add_argument("module")
    rebuild_knowledge.add_argument("--submodule")
    rebuild_knowledge.set_defaults(handler=command_knowledge_rebuild_index)
    update_knowledge = knowledge_commands.add_parser("update")
    update_knowledge.add_argument("module")
    update_knowledge.add_argument("document_id")
    update_knowledge.add_argument("--submodule")
    update_knowledge.add_argument("--title")
    update_knowledge.add_argument("--topic")
    update_knowledge.add_argument("--answer")
    update_knowledge.add_argument("--source", action="append", default=[])
    update_knowledge.add_argument("--question-id", action="append", default=[])
    update_knowledge.add_argument("--evidence-status", choices=KNOWLEDGE_EVIDENCE_STATUSES)
    update_knowledge.add_argument("--dry-run", action="store_true")
    update_knowledge.set_defaults(handler=command_knowledge_update)
    archive_knowledge = knowledge_commands.add_parser("archive")
    archive_knowledge.add_argument("module")
    archive_knowledge.add_argument("document_id")
    archive_knowledge.add_argument("--submodule")
    archive_knowledge.add_argument("--reason", required=True)
    archive_knowledge.add_argument("--dry-run", action="store_true")
    archive_knowledge.set_defaults(handler=command_knowledge_archive)
    validate_knowledge = knowledge_commands.add_parser("validate")
    validate_knowledge.add_argument("module")
    validate_knowledge.add_argument("--submodule")
    validate_knowledge.add_argument("--document-id")
    validate_knowledge.set_defaults(handler=command_knowledge_validate)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.handler(args)
    except UserError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
