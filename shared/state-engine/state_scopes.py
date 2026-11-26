#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Optional scope-aware review workflow helpers.

This module deliberately uses only the Python standard library and does not
import the state_utils facade.  The file is copied into initialized projects,
so it must also work when imported directly from ``state/``.

A scope is a deterministic, reviewable unit below an iteration node.  Legacy
N0-N8 state remains authoritative when no scope is supplied.
"""
from __future__ import annotations

import hashlib
import json
import ntpath
import os
import posixpath
import re
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


STATE_DIR = "state"
STATE_FILE = "state/decision_log.json"
REGISTRY_FILE = "state/registry.json"
REVIEWS_DIR = "state/reviews"
SCOPED_NODES = {"N4", "N5", "N7", "N8"}
CODE_NODES = {"N4", "N5"}
# The scope layer keeps the common iteration phases while making the paper
# content/format ordering explicit.  N4/N5 do not use FORMAT; N7/N8 do.
COMMON_PHASES = ("DISPATCH", "IMPLEMENT", "RUN", "REVIEW", "SCORE", "DECIDE")
PAPER_PHASES = ("DISPATCH", "CONTENT_REVIEW", "FORMAT_REVIEW_INITIAL", "AGGREGATE", "CONTENT_REPAIR", "CONTENT_REVIEW_FINAL", "FORMAT_REPAIR", "RUN", "FORMAT_REVIEW_FINAL", "JOIN", "SCORE", "DECIDE")
REQUIRED_PHASES = COMMON_PHASES
ALL_PHASES = ("PLAN",) + tuple(dict.fromkeys(COMMON_PHASES + PAPER_PHASES + ("AGGREGATE", "PROMOTE")))


def required_phases_for(node: str) -> Tuple[str, ...]:
    return PAPER_PHASES if node in {"N7", "N8"} else COMMON_PHASES
COMPLETE_STATUSES = {"completed", "passed", "PASS", "promoted"}
_SAFE_SCOPE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_QUESTION_RE = re.compile(r"^(?:question|q|problem)[_-]?([1-4])$", re.IGNORECASE)


class ScopeError(ValueError):
    """Raised when a scope request is invalid or cannot be planned safely."""


def utc_now() -> str:
    """Return a stable, UTC-only timestamp for manifests and plans."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def safe_scope_id(scope_id: str) -> str:
    """Validate a scope identifier before using it as a directory component.

    Scope IDs intentionally use a small ASCII alphabet.  This rejects both
    POSIX and Windows absolute paths as well as ``..`` traversal components.
    """
    value = str(scope_id or "").strip()
    if not value or not _SAFE_SCOPE_RE.fullmatch(value):
        raise ScopeError(
            "scope_id must match [A-Za-z0-9][A-Za-z0-9_-]{0,63}; absolute and '..' paths are rejected"
        )
    if value in {".", ".."} or ".." in value:
        raise ScopeError("scope_id cannot contain '..'")
    return value


def safe_repo_relative(path: str) -> str:
    """Return a normalized repository-relative path or reject it.

    Both slash conventions are checked because projects are commonly created
    on one platform and reviewed on another.  Empty and parent components
    are rejected instead of relying on filesystem resolution.
    """
    value = str(path or "").strip().replace("\\", "/")
    if not value or posixpath.isabs(value) or ntpath.isabs(value):
        raise ScopeError("repository paths must be relative")
    if re.match(r"^[A-Za-z]:", value) or value.startswith("//"):
        raise ScopeError("repository paths must not contain a drive or UNC prefix")
    parts = value.split("/")
    if any(part == ".." for part in parts):
        raise ScopeError("repository paths cannot contain '..'")
    normalized = posixpath.normpath(value)
    if normalized in {"", ".", ".."} or normalized.startswith("../"):
        raise ScopeError("repository path resolves outside the repository")
    return normalized.replace("\\", "/")


def _repo_path(root: str, relative: str) -> str:
    return os.path.join(os.path.abspath(root), safe_repo_relative(relative).replace("/", os.sep))


def _load_json(path: str, default: Any = None) -> Any:
    if not os.path.isfile(path):
        return default
    with open(path, "r", encoding="utf-8") as stream:
        return json.load(stream)


def _atomic_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(path) or ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.replace(temp_path, path)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def _atomic_json(path: str, payload: Any) -> None:
    _atomic_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _digest_path(root: str, relative: str) -> Optional[str]:
    """Hash a file or a deterministic recursive directory snapshot."""
    full = _repo_path(root, relative)
    if os.path.isfile(full):
        return _sha256_file(full)
    if not os.path.isdir(full):
        return None
    entries: List[str] = []
    for directory, dirnames, filenames in os.walk(full):
        dirnames[:] = sorted(d for d in dirnames if d not in {".git", "__pycache__", ".venv"})
        for filename in sorted(filenames):
            path = os.path.join(directory, filename)
            if filename.endswith((".pyc", ".pyo")):
                continue
            rel = os.path.relpath(path, os.path.abspath(root)).replace(os.sep, "/")
            entries.append(rel + ":" + _sha256_file(path))
    return _sha256_bytes("\n".join(entries).encode("utf-8"))


def _registry_hash(root: str) -> str:
    path = os.path.join(os.path.abspath(root), REGISTRY_FILE.replace("/", os.sep))
    return _sha256_file(path) if os.path.isfile(path) else ""


def _stable_run_id(node: str, round_no: int, scope_id: str, attempt: int) -> str:
    return "scope-{0}-r{1}-{2}-a{3}".format(node.lower(), round_no, scope_id, attempt)


def _slug(value: str, fallback: str) -> str:
    value = value.lower().replace("-", "_")
    value = re.sub(r"[^a-z0-9_]+", "_", value).strip("_")
    return value or fallback


def _question_scope(value: str) -> Optional[str]:
    match = _QUESTION_RE.fullmatch(value.strip())
    return "question_" + match.group(1) if match else None


def _list_files(root: str, relative: str) -> List[str]:
    full = _repo_path(root, relative)
    if os.path.isfile(full):
        return [safe_repo_relative(relative)]
    if not os.path.isdir(full):
        return [safe_repo_relative(relative)]
    files: List[str] = []
    for directory, dirnames, filenames in os.walk(full):
        dirnames[:] = sorted(d for d in dirnames if d not in {".git", "__pycache__", ".venv"})
        for filename in sorted(filenames):
            if filename.endswith((".pyc", ".pyo")):
                continue
            path = os.path.relpath(os.path.join(directory, filename), os.path.abspath(root))
            files.append(safe_repo_relative(path))
    return files or [safe_repo_relative(relative)]


def _read_text(root: str, relative: str) -> str:
    path = _repo_path(root, relative)
    if not os.path.isfile(path):
        return ""
    with open(path, "r", encoding="utf-8", errors="replace") as stream:
        return stream.read()


def _input_files_from_main(root: str) -> List[str]:
    main = "ReportPaper/LaTeX/main.tex"
    text = _read_text(root, main)
    paths = {main}
    # Drop comments before parsing \input/\include directives.  The generated
    # template contains commented examples that must not become work scopes.
    active_lines = []
    for line in text.splitlines():
        active_lines.append(line.split("%", 1)[0])
    active = "\n".join(active_lines)
    for match in re.finditer(r"\\(?:input|include)\s*\{([^{}]+)\}", active):
        raw = match.group(1).strip()
        if not raw:
            continue
        if not raw.lower().endswith(".tex"):
            raw += ".tex"
        candidate = "ReportPaper/LaTeX/" + raw
        try:
            paths.add(safe_repo_relative(candidate))
        except ScopeError:
            # A LaTeX include outside the canonical tree is not a safe review
            # input; it is reported through the main file only.
            continue
    sections_dir = os.path.join(os.path.abspath(root), "ReportPaper", "LaTeX", "sections")
    if os.path.isdir(sections_dir):
        for filename in sorted(os.listdir(sections_dir)):
            if filename.lower().endswith(".tex"):
                paths.add(safe_repo_relative("ReportPaper/LaTeX/sections/" + filename))
    return sorted(paths)


def _section_scope(root: str, relative: str) -> Dict[str, Any]:
    stem = os.path.splitext(os.path.basename(relative))[0]
    scope_id = safe_scope_id("section_" + _slug(stem, "section"))
    return {"scope_id": scope_id, "scope_kind": "section", "inputs": [relative], "target_ref": relative}


def _model_solution_scopes(root: str, relative: str, max_chars: int) -> List[Dict[str, Any]]:
    text = _read_text(root, relative)
    if len(text) <= max_chars:
        result = _section_scope(root, relative)
        result["scope_kind"] = "section"
        return [result]

    # Prefer LaTeX subsections and question headings.  The fallback chunking
    # is deterministic and keeps each chunk tied to the original source file.
    heading_re = re.compile(
        r"(?m)^(?P<header>\\(?:subsection|subsubsection)\s*(?:\[[^\]]*\])?\s*\{[^\n]+\})"
    )
    matches = list(heading_re.finditer(text))
    chunks: List[Tuple[str, str]] = []
    if matches:
        prefix = text[: matches[0].start()].strip()
        if prefix:
            chunks.append(("preamble", prefix))
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            header = match.group("header")
            title_match = re.search(r"\{([^{}]+)\}", header)
            title = title_match.group(1) if title_match else "part_" + str(index + 1)
            chunks.append((title, text[match.start():end].strip()))
    else:
        chunks = [("part_" + str(index + 1), text[start:start + max_chars].strip())
                  for index, start in enumerate(range(0, len(text), max_chars))]

    result: List[Dict[str, Any]] = []
    question_number = 0
    for index, (title, chunk) in enumerate(chunks, 1):
        question_match = re.search(r"(?:问题|question|problem|q\s*)\s*[_-]?(\d+)", title, re.IGNORECASE)
        if question_match:
            question_number = int(question_match.group(1))
        elif question_number == 0:
            question_number = index
        suffix = "q" + str(question_number) if question_number <= 99 else "part_" + str(index)
        if len(chunk) > max_chars:
            # A very long subsection is split again, retaining the question
            # hint so dispatchers can still route it to the right question.
            for part, start in enumerate(range(0, len(chunk), max_chars), 1):
                piece = chunk[start:start + max_chars]
                sid = safe_scope_id("section_model_solution_" + suffix + "_part_" + str(part))
                result.append({"scope_id": sid, "scope_kind": "model_solution_subsection",
                               "inputs": [relative], "target_ref": relative,
                               "source_fragment": {"title": title, "part": part, "text_sha256": _sha256_bytes(piece.encode("utf-8"))}})
        else:
            sid = safe_scope_id("section_model_solution_" + suffix)
            result.append({"scope_id": sid, "scope_kind": "model_solution_subsection",
                           "inputs": [relative], "target_ref": relative,
                           "source_fragment": {"title": title, "text_sha256": _sha256_bytes(chunk.encode("utf-8"))}})
    # Distinct subsection titles can map to the same question number.  Keep
    # names unique without depending on filesystem order beyond sorted input.
    seen: Dict[str, int] = {}
    for item in result:
        base = item["scope_id"]
        seen[base] = seen.get(base, 0) + 1
        if seen[base] > 1:
            item["scope_id"] = safe_scope_id(base + "_part_" + str(seen[base]))
    return result


def _plan_code_scopes(root: str, target: Optional[str]) -> List[Dict[str, Any]]:
    selected = _question_scope(target) if target else None
    if target and selected is None:
        candidate = target.strip().replace("\\", "/")
        if candidate.startswith("Code/problem_"):
            match = re.search(r"problem_([1-4])(?:/|$)", candidate)
            selected = "question_" + match.group(1) if match else None
        if selected is None:
            try:
                selected = safe_scope_id(candidate)
            except ScopeError as exc:
                raise ScopeError("invalid code scope target: " + str(exc))
    ids = [selected] if selected else ["question_1", "question_2", "question_3", "question_4"]
    result = []
    for scope_id in ids:
        number = scope_id.rsplit("_", 1)[-1]
        relative = "Code/problem_" + number
        inputs = _list_files(root, relative)
        result.append({"scope_id": safe_scope_id(scope_id), "scope_kind": "question",
                       "inputs": inputs, "target_ref": relative})
    return result


def _plan_paper_scopes(root: str, target: Optional[str], mode: str, max_chars: int) -> List[Dict[str, Any]]:
    input_files = _input_files_from_main(root)
    result: List[Dict[str, Any]] = []
    for relative in input_files:
        if relative.endswith("/model_solution.tex") and mode == "adaptive":
            result.extend(_model_solution_scopes(root, relative, max_chars))
        elif relative.startswith("ReportPaper/LaTeX/sections/") and relative.lower().endswith(".tex"):
            result.append(_section_scope(root, relative))
    if not result:
        result.append({"scope_id": "section_main", "scope_kind": "section",
                       "inputs": ["ReportPaper/LaTeX/main.tex"], "target_ref": "ReportPaper/LaTeX/main.tex"})
    if target:
        normalized = target.replace("\\", "/").strip()
        target_id = normalized
        if normalized.startswith("sections/"):
            target_id = "section_" + _slug(os.path.splitext(os.path.basename(normalized))[0], "section")
        elif normalized.endswith(".tex"):
            target_id = "section_" + _slug(os.path.splitext(os.path.basename(normalized))[0], "section")
        try:
            target_id = safe_scope_id(target_id)
        except ScopeError as exc:
            raise ScopeError("invalid paper scope target: " + str(exc))
        result = [item for item in result if item["scope_id"] == target_id or item["scope_id"].startswith(target_id + "_")]
        if not result:
            raise ScopeError("target does not match any paper section: " + target)
    return result


def discover_scopes(root: str, node: str, target: Optional[str] = None,
                    mode: str = "adaptive", max_chars: int = 12000) -> List[Dict[str, Any]]:
    """Discover deterministic scopes for N4/N5/N7/N8."""
    if node not in SCOPED_NODES:
        raise ScopeError("scope workflow supports only N4, N5, N7, and N8")
    if mode not in {"adaptive", "static"}:
        raise ScopeError("mode must be adaptive or static")
    if max_chars < 1:
        raise ScopeError("max_chars must be positive")
    if node in CODE_NODES:
        return _plan_code_scopes(root, target)
    return _plan_paper_scopes(root, target, mode, max_chars)


def _workspace_relative(node: str, round_no: int, scope_id: str) -> str:
    return "{}/{}/round_{}/{}".format(REVIEWS_DIR, node, round_no, safe_scope_id(scope_id))


def _manifest_path(root: str, node: str, round_no: int, scope_id: str) -> str:
    return os.path.join(_repo_path(root, _workspace_relative(node, round_no, scope_id)), "review_workspace_manifest.json")


def _manifest_files(root: str, node: str, round_no: int, scope_id: Optional[str] = None) -> List[str]:
    base_rel = "{}/{}/round_{}".format(REVIEWS_DIR, node, round_no)
    base = _repo_path(root, base_rel)
    if scope_id is not None:
        return [_manifest_path(root, node, round_no, safe_scope_id(scope_id))] if os.path.isfile(_manifest_path(root, node, round_no, safe_scope_id(scope_id))) else []
    if not os.path.isdir(base):
        return []
    result = []
    for name in sorted(os.listdir(base)):
        if not _SAFE_SCOPE_RE.fullmatch(name):
            continue
        path = os.path.join(base, name, "review_workspace_manifest.json")
        if os.path.isfile(path):
            result.append(path)
    return result


def _read_manifest(path: str) -> Dict[str, Any]:
    manifest = _load_json(path)
    if not isinstance(manifest, dict):
        raise ScopeError("invalid review workspace manifest: " + path)
    return manifest


def _record_scope_state(root: str, records: Sequence[Dict[str, Any]]) -> None:
    path = os.path.join(os.path.abspath(root), STATE_FILE.replace("/", os.sep))
    if not os.path.isfile(path):
        return
    state = _load_json(path, {})
    if not isinstance(state, dict):
        return
    scope_records = state.setdefault("scopes", [])
    if not isinstance(scope_records, list):
        scope_records = []
        state["scopes"] = scope_records
    for record in records:
        key = (record.get("node"), record.get("round"), record.get("scope_id"))
        scope_records[:] = [item for item in scope_records
                            if (item.get("node"), item.get("round"), item.get("scope_id")) != key]
        scope_records.append(dict(record))
    scope_records.sort(key=lambda item: (str(item.get("node")), int(item.get("round", 0)), str(item.get("scope_id"))))
    if isinstance(state.get("meta"), dict):
        state["meta"]["seq"] = int(state["meta"].get("seq", 0)) + 1
        state["meta"]["updated_at"] = utc_now()
    _atomic_json(path, state)


def _phase_status_for(node: str, previous: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    statuses = {phase: "pending" for phase in required_phases_for(node)}
    statuses["PLAN"] = "completed"
    if isinstance(previous, dict) and isinstance(previous.get("phase_status"), dict):
        statuses.update(previous["phase_status"])
    return statuses


def _write_handoff(workspace: str, manifest: Dict[str, Any]) -> None:
    lines = [
        "# Scoped review handoff",
        "",
        "> This workspace is machine-generated; paths are repository-relative.",
        "",
        "| field | value |",
        "|------|-------|",
        "| node | {0} |".format(manifest["node"]),
        "| round | {0} |".format(manifest["round"]),
        "| scope_id | {0} |".format(manifest["scope_id"]),
        "| scope_kind | {0} |".format(manifest["scope_kind"]),
        "| phase | {0} |".format(manifest["phase"]),
        "| status | {0} |".format(manifest["status"]),
        "| attempt | {0} |".format(manifest["attempt"]),
        "| run_id | {0} |".format(manifest["run_id"]),
        "| registry_sha256 | {0} |".format(manifest["registry_sha256"] or "-"),
        "| base_artifact_sha256 | {0} |".format(manifest["base_artifact_sha256"]),
        "",
        "## Inputs",
        "",
    ]
    lines.extend("- `{}`".format(path) for path in manifest["inputs"])
    lines.extend(["", "## Required phases", ""])
    lines.extend("- `{}`: `{}`".format(phase, manifest["phase_status"].get(phase, "pending")) for phase in ALL_PHASES)
    _atomic_text(os.path.join(workspace, "handoff.md"), "\n".join(lines) + "\n")


def _write_workspace(root: str, node: str, round_no: int, item: Dict[str, Any],
                     mode: str, max_chars: int, attempt: int, run_id: Optional[str]) -> Dict[str, Any]:
    scope_id = safe_scope_id(item["scope_id"])
    workspace_rel = _workspace_relative(node, round_no, scope_id)
    workspace = _repo_path(root, workspace_rel)
    os.makedirs(workspace, exist_ok=True)
    phase_dirs = ("content_review", "format_review", "content_repair", "format_repair", "re_review", "evidence")
    for phase_dir in phase_dirs:
        os.makedirs(os.path.join(workspace, phase_dir), exist_ok=True)
    inputs = sorted({safe_repo_relative(path) for path in item.get("inputs", [])})
    source_hashes = {path: _digest_path(root, path) for path in inputs}
    base_hash = _sha256_bytes(json.dumps({"node": node, "round": round_no,
                                          "scope_id": scope_id, "source_hashes": source_hashes},
                                         sort_keys=True, ensure_ascii=False).encode("utf-8"))
    manifest_path = os.path.join(workspace, "review_workspace_manifest.json")
    previous = _load_json(manifest_path, {})
    effective_attempt = int(previous.get("attempt", attempt)) if isinstance(previous, dict) else attempt
    effective_run_id = (previous.get("run_id") if isinstance(previous, dict) else None) or run_id or _stable_run_id(node, round_no, scope_id, effective_attempt)
    phase_status = _phase_status_for(node, previous)
    input_manifest = {
        "schema_version": "scope-input/1.0", "version": "1.0", "generated_at": utc_now(),
        "node": node, "round": round_no, "scope_id": scope_id,
        "attempt": effective_attempt, "run_id": effective_run_id,
        "inputs": [{"path": path, "sha256": source_hashes[path]} for path in inputs],
        "source_fragment": item.get("source_fragment"), "target_ref": item.get("target_ref"),
        "context_budget": max_chars, "excluded_full_document": True,
    }
    input_path = os.path.join(workspace, "input_manifest.json")
    _atomic_json(input_path, input_manifest)
    input_hash = _sha256_file(input_path)
    manifest = {
        "schema_version": "review-workspace/1.0", "version": "1.0", "created_at": (previous.get("created_at") if isinstance(previous, dict) else None) or utc_now(),
        "updated_at": utc_now(), "node": node, "round": round_no, "scope_id": scope_id,
        "scope_key": "{}:r{}:{}".format(node, round_no, scope_id),
        "scope_kind": item.get("scope_kind", "scope"), "target_ref": item.get("target_ref"),
        "output_scope": workspace_rel, "inputs": inputs, "source_hashes": source_hashes,
        "registry_sha256": _registry_hash(root), "base_artifact_sha256": base_hash,
        "input_manifest_sha256": input_hash, "phase": "PLAN", "status": "planned",
        "phase_status": phase_status, "required_phases": list(required_phases_for(node)),
        "context_budget": max_chars, "included_context_refs": inputs, "excluded_full_document": True,
        "dependencies": [], "report_refs": [], "changed_files": [], "merge_status": "pending",
        "attempt": effective_attempt, "run_id": effective_run_id, "mode": mode,
        "max_chars": max_chars, "source_fragment": item.get("source_fragment"),
    }
    _atomic_json(manifest_path, manifest)
    dispatch = {
        "version": "1.0", "generated_at": utc_now(), "node": node, "round": round_no,
        "scope_id": scope_id, "scope_key": manifest["scope_key"], "phase": "DISPATCH",
        "status": "pending", "attempt": effective_attempt, "run_id": effective_run_id,
        "registry_sha256": manifest["registry_sha256"], "input_manifest": workspace_rel + "/input_manifest.json",
        "tasks": [{"kind": "review", "target_ref": item.get("target_ref"), "inputs": inputs}],
    }
    _atomic_json(os.path.join(workspace, "dispatch_plan.json"), dispatch)
    aggregate = {
        "version": "1.0", "generated_at": utc_now(), "node": node, "round": round_no,
        "scope_id": scope_id, "scope_key": manifest["scope_key"], "phase": "AGGREGATE",
        "status": "pending", "attempt": effective_attempt, "run_id": effective_run_id,
        "required_phases": list(required_phases_for(node)),
        "missing_phases": list(required_phases_for(node)),
    }
    _atomic_json(os.path.join(workspace, "aggregate_plan.json"), aggregate)
    _write_handoff(workspace, manifest)
    return {"scope_id": scope_id, "scope_kind": manifest["scope_kind"], "workspace": workspace_rel,
            "inputs": inputs, "target_ref": item.get("target_ref"), "phase": manifest["phase"],
            "status": manifest["status"], "attempt": effective_attempt, "run_id": effective_run_id,
            "base_artifact_sha256": base_hash, "input_manifest_sha256": input_hash,
            "registry_sha256": manifest["registry_sha256"]}


def plan_scopes(root: str, node: str, round_no: int, mode: str = "adaptive",
                target: Optional[str] = None, scope_id: Optional[str] = None,
                max_chars: int = 12000, attempt: int = 1,
                run_id: Optional[str] = None) -> Dict[str, Any]:
    """Create deterministic scope workspaces and all machine handoff files."""
    if node not in SCOPED_NODES:
        raise ScopeError("scope workflow supports only N4, N5, N7, and N8")
    if int(round_no) < 1:
        raise ScopeError("round must be a positive integer")
    if int(attempt) < 1:
        raise ScopeError("attempt must be a positive integer")
    if target:
        # Explicitly reject traversal before the node-specific target parser.
        target_text = str(target)
        if "/" in target_text or "\\" in target_text or target_text.startswith(".") or re.match(r"^[A-Za-z]:", target_text):
            safe_repo_relative(target_text)
    if scope_id:
        scope_id = safe_scope_id(scope_id)
    discovered = discover_scopes(root, node, target=target, mode=mode, max_chars=int(max_chars))
    if scope_id:
        discovered = [item for item in discovered if item["scope_id"] == scope_id]
        if not discovered:
            raise ScopeError("scope_id does not match any discovered scope: " + scope_id)
    discovered = sorted(discovered, key=lambda item: item["scope_id"])
    output: List[Dict[str, Any]] = []
    for item in discovered:
        output.append(_write_workspace(root, node, int(round_no), item, mode, int(max_chars), int(attempt), run_id))
    base_rel = "{}/{}/round_{}".format(REVIEWS_DIR, node, int(round_no))
    base_dir = _repo_path(root, base_rel)
    dispatch_rel = base_rel + "/dispatch_plan.json"
    aggregate_rel = base_rel + "/aggregate_plan.json"
    generated = utc_now()
    dispatch = {
        "version": "1.0", "generated_at": generated, "node": node, "round": int(round_no),
        "scope_id": scope_id, "scope_key": "{}:r{}".format(node, int(round_no)),
        "scope_kind": "batch", "phase": "DISPATCH", "status": "planned",
        "attempt": int(attempt), "run_id": run_id or "batch-{}-r{}".format(node.lower(), int(round_no)),
        "registry_sha256": _registry_hash(root), "scopes": output,
    }
    aggregate = {
        "version": "1.0", "generated_at": generated, "node": node, "round": int(round_no),
        "scope_id": scope_id, "scope_key": "{}:r{}".format(node, int(round_no)),
        "scope_kind": "batch", "phase": "AGGREGATE", "status": "pending",
        "attempt": int(attempt), "run_id": run_id or "batch-{}-r{}".format(node.lower(), int(round_no)),
        "registry_sha256": _registry_hash(root), "required_phases": list(required_phases_for(node)),
        "scopes": [item["scope_id"] for item in output], "missing_phases": [],
    }
    _atomic_json(os.path.join(base_dir, "dispatch_plan.json"), dispatch)
    _atomic_json(os.path.join(base_dir, "aggregate_plan.json"), aggregate)
    _record_scope_state(root, [{"node": node, "round": int(round_no), "scope_id": item["scope_id"],
                               "scope_key": "{}:r{}:{}".format(node, int(round_no), item["scope_id"]),
                               "workspace": item["workspace"], "status": item["status"],
                               "phase": item["phase"], "attempt": item["attempt"], "run_id": item["run_id"]}
                              for item in output])
    return {"version": "1.0", "generated_at": generated, "node": node, "round": int(round_no),
            "mode": mode, "target": target, "scope_id": scope_id, "registry_sha256": _registry_hash(root),
            "required_phases": list(required_phases_for(node)), "dispatch_plan": dispatch_rel,
            "aggregate_plan": aggregate_rel, "scopes": output}


def _missing_phases(manifest: Dict[str, Any]) -> List[str]:
    statuses = manifest.get("phase_status") or {}
    phases = manifest.get("required_phases") or list(REQUIRED_PHASES)
    return [phase for phase in phases if statuses.get(phase) not in COMPLETE_STATUSES]


def _phase_name(value: str) -> str:
    """Normalize human phase spellings used by Agent prompts and CLI calls."""
    aliases = {
        "content_review": "CONTENT_REVIEW", "content-repair": "CONTENT_REPAIR",
        "content_repair": "CONTENT_REPAIR", "format_review": "FORMAT_REVIEW_INITIAL",
        "format_review_initial": "FORMAT_REVIEW_INITIAL", "format_review_final": "FORMAT_REVIEW_FINAL",
        "content_review_final": "CONTENT_REVIEW_FINAL", "content_review_initial": "CONTENT_REVIEW", "join": "JOIN", "join_review": "JOIN",
        "format-repair": "FORMAT_REPAIR", "format_repair": "FORMAT_REPAIR",
        "join_review": "JOIN", "join-review": "JOIN", "re_review": "REVIEW",
        "re-review": "REVIEW", "run": "RUN", "review": "REVIEW",
    }
    raw = str(value or "").strip()
    return aliases.get(raw.lower(), raw.upper())


def _phase_prerequisites(node: str, phase: str) -> Tuple[str, ...]:
    phases = required_phases_for(node)
    try:
        index = phases.index(phase)
    except ValueError:
        return ()
    return tuple(phases[:index])


def update_scope_phase(root: str, node: str, round_no: int, scope_id: str,
                      phase: str, status: str = "completed", *, force: bool = False) -> Dict[str, Any]:
    """Update one scope phase without touching parent status.

    Completed phases are ordered.  This is the machine guard that prevents a
    typesetting write from running before content repair/review has passed.
    ``force`` is reserved for recovery/administrative repair and must be
    explicitly supplied by the caller.
    """
    phase = _phase_name(phase)
    if phase not in ALL_PHASES:
        raise ScopeError("unknown scope phase: " + phase)
    path = _manifest_path(root, node, int(round_no), safe_scope_id(scope_id))
    if not os.path.isfile(path):
        raise ScopeError("scope workspace does not exist: " + _workspace_relative(node, int(round_no), scope_id))
    manifest = _read_manifest(path)
    if status in COMPLETE_STATUSES and not force:
        missing = [item for item in _phase_prerequisites(node, phase)
                   if manifest.get("phase_status", {}).get(item) not in COMPLETE_STATUSES]
        if missing:
            raise ScopeError("phase order blocked: {} requires {}".format(phase, ", ".join(missing)))
    manifest.setdefault("phase_status", {})[phase] = status
    manifest["phase"] = phase
    manifest["status"] = status
    manifest["updated_at"] = utc_now()
    _atomic_json(path, manifest)
    _write_handoff(os.path.dirname(path), manifest)
    return manifest


def write_scope_report(root: str, node: str, round_no: int, scope_id: str,
                       phase: str, payload: Dict[str, Any], run_id: Optional[str] = None) -> str:
    """Write a report inside the scope workspace and register its reference."""
    safe_id = safe_scope_id(scope_id)
    phase_dir = re.sub(r"[^a-z0-9_-]+", "_", str(phase).lower()).strip("_") or "report"
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", phase_dir):
        raise ScopeError("invalid scope report phase")
    manifest_path = _manifest_path(root, node, int(round_no), safe_id)
    if not os.path.isfile(manifest_path):
        raise ScopeError("scope workspace does not exist")
    manifest = _read_manifest(manifest_path)
    report_id = run_id or "{}-{}-{}".format(node.lower(), safe_id, utc_now().replace(":", "").replace("-", ""))
    rel = _workspace_relative(node, int(round_no), safe_id) + "/" + phase_dir + "/" + report_id + ".json"
    payload = dict(payload)
    payload.update({"scope_id": safe_id, "scope_key": manifest.get("scope_key"),
                    "node": node, "round": int(round_no), "phase": _phase_name(phase),
                    "run_id": report_id, "timestamp": payload.get("timestamp") or utc_now()})
    _atomic_json(_repo_path(root, rel), payload)
    refs = manifest.setdefault("report_refs", [])
    if rel not in refs:
        refs.append(rel)
    manifest["updated_at"] = utc_now()
    _atomic_json(manifest_path, manifest)
    _write_handoff(os.path.dirname(manifest_path), manifest)
    return rel


def record_empty_return(root: str, node: str, round_no: int, scope_id: str,
                        attempt: int, reason: str, last_result: Any = None) -> str:
    """Persist an EMPTY_RETURN recovery record and block the scope."""
    safe_id = safe_scope_id(scope_id)
    path = _manifest_path(root, node, int(round_no), safe_id)
    if not os.path.isfile(path):
        raise ScopeError("scope workspace does not exist")
    manifest = _read_manifest(path)
    recovery = {"schema_version": "scope-recovery/1.0", "status": "BLOCKED",
                "reason_code": "EMPTY_RETURN", "node": node, "round": int(round_no),
                "scope_id": safe_id, "attempt": int(attempt), "reason": str(reason),
                "last_result": last_result, "timestamp": utc_now()}
    rel = _workspace_relative(node, int(round_no), safe_id) + "/recovery.json"
    _atomic_json(_repo_path(root, rel), recovery)
    manifest["status"] = "BLOCKED"
    manifest["phase"] = "RECOVERY"
    manifest["attempt"] = int(attempt)
    manifest.setdefault("phase_status", {})["RECOVERY"] = "BLOCKED"
    manifest["report_refs"] = list(dict.fromkeys(manifest.get("report_refs", []) + [rel]))
    manifest["updated_at"] = recovery["timestamp"]
    _atomic_json(path, manifest)
    _write_handoff(os.path.dirname(path), manifest)
    return rel


def aggregate_scopes(root: str, node: str, round_no: int,
                     scope_id: Optional[str] = None) -> Dict[str, Any]:
    """Validate required phases for one scope or all scopes in a round."""
    paths = _manifest_files(root, node, int(round_no), scope_id)
    if not paths:
        raise ScopeError("no scope workspaces found for {}/round{}".format(node, round_no))
    records = []
    missing_all = []
    for path in paths:
        manifest = _read_manifest(path)
        missing = _missing_phases(manifest)
        if missing:
            missing_all.append({"scope_id": manifest.get("scope_id"), "phases": missing})
        records.append({"scope_id": manifest.get("scope_id"), "workspace": manifest.get("output_scope"),
                        "phase": "AGGREGATE", "status": "PASS" if not missing else "BLOCKED",
                        "missing_phases": missing, "attempt": manifest.get("attempt"),
                        "run_id": manifest.get("run_id")})
    status = "PASS" if not missing_all else "BLOCKED"
    generated = utc_now()
    plan = {"version": "1.0", "generated_at": generated, "node": node, "round": int(round_no),
            "scope_id": scope_id, "scope_key": "{}:r{}".format(node, int(round_no)),
            "scope_kind": "batch" if scope_id is None else "scope", "phase": "AGGREGATE", "status": status,
            "attempt": max(int(item.get("attempt") or 1) for item in records),
            "run_id": "aggregate-{}-r{}".format(node.lower(), int(round_no)),
            "registry_sha256": _registry_hash(root), "required_phases": list(required_phases_for(node)),
            "scopes": records, "missing_phases": missing_all}
    round_rel = "{}/{}/round_{}".format(REVIEWS_DIR, node, int(round_no))
    _atomic_json(_repo_path(root, round_rel + "/aggregate_plan.json"), plan)
    for path in paths:
        manifest = _read_manifest(path)
        missing = _missing_phases(manifest)
        if not missing:
            manifest.setdefault("phase_status", {})["AGGREGATE"] = "completed"
            manifest["phase"] = "AGGREGATE"
            manifest["status"] = "aggregated"
            manifest["updated_at"] = generated
            _atomic_json(path, manifest)
            _write_handoff(os.path.dirname(path), manifest)
    return plan


def _set_parent_completed(root: str, node: str) -> None:
    path = os.path.join(os.path.abspath(root), STATE_FILE.replace("/", os.sep))
    state = _load_json(path)
    if not isinstance(state, dict):
        return
    nodes = state.setdefault("nodes", {})
    node_state = nodes.setdefault(node, {})
    node_state["status"] = "completed"
    node_state["scope_promoted_at"] = utc_now()
    stages = state.setdefault("stages", {})
    stage_map = {"N4": "4_solving", "N5": "5_tuning", "N7": "7_writing", "N8": "8_review"}
    stage = stages.get(stage_map.get(node, ""))
    if isinstance(stage, dict):
        stage["status"] = "completed"
        stage["completed_at"] = node_state["scope_promoted_at"]
    if isinstance(state.get("meta"), dict):
        state["meta"]["seq"] = int(state["meta"].get("seq", 0)) + 1
        state["meta"]["updated_at"] = node_state["scope_promoted_at"]
    _atomic_json(path, state)


def promote_scopes(root: str, node: str, round_no: int,
                   scope_id: Optional[str] = None) -> Dict[str, Any]:
    """Promote validated scope(s); complete the parent only after all pass."""
    selected_paths = _manifest_files(root, node, int(round_no), scope_id)
    all_paths = _manifest_files(root, node, int(round_no), None)
    if not selected_paths:
        raise ScopeError("no scope workspaces found for promotion")
    promoted = []
    blocked = []
    generated = utc_now()
    for path in selected_paths:
        manifest = _read_manifest(path)
        missing = _missing_phases(manifest)
        if missing:
            blocked.append({"scope_id": manifest.get("scope_id"), "missing_phases": missing})
            continue
        manifest.setdefault("phase_status", {})["PROMOTE"] = "completed"
        manifest["phase"] = "PROMOTE"
        manifest["status"] = "promoted"
        manifest["promoted_at"] = generated
        manifest["updated_at"] = generated
        _atomic_json(path, manifest)
        _write_handoff(os.path.dirname(path), manifest)
        promoted.append({"scope_id": manifest.get("scope_id"), "workspace": manifest.get("output_scope"),
                         "status": "PROMOTED", "attempt": manifest.get("attempt"), "run_id": manifest.get("run_id")})
    all_promoted = True
    for path in all_paths:
        manifest = _read_manifest(path)
        if manifest.get("status") != "promoted" or _missing_phases(manifest):
            all_promoted = False
            break
    if all_promoted and not blocked:
        _set_parent_completed(root, node)
    status = "PROMOTED" if promoted and not blocked else "BLOCKED"
    if not selected_paths:
        status = "BLOCKED"
    return {"version": "1.0", "generated_at": generated, "node": node, "round": int(round_no),
            "scope_id": scope_id, "scope_key": "{}:r{}".format(node, int(round_no)),
            "scope_kind": "batch" if scope_id is None else "scope", "phase": "PROMOTE", "status": status,
            "attempt": max([int(item.get("attempt") or 1) for item in promoted + blocked] or [1]),
            "run_id": "promote-{}-r{}".format(node.lower(), int(round_no)),
            "registry_sha256": _registry_hash(root), "required_phases": list(required_phases_for(node)),
            "promoted": promoted, "blocked": blocked, "all_scopes_promoted": all_promoted,
            "parent_completed": bool(all_promoted and not blocked)}


def _scope_error(exc: Exception) -> None:
    raise SystemExit("[state_utils] scope workflow: {}".format(exc))


def cmd_scope_plan(args: Any) -> None:
    try:
        requested_kind = getattr(args, "scope_kind", None)
        mode = getattr(args, "mode", "adaptive")
        if requested_kind == "static":
            mode = "static"
        plan = plan_scopes(os.path.abspath(args.dir), args.node, args.round, mode=mode,
                           target=args.target, scope_id=getattr(args, "scope_id", None),
                           max_chars=args.max_chars, attempt=args.attempt, run_id=args.run_id)
    except (ScopeError, OSError, ValueError) as exc:
        _scope_error(exc)
    print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))


def cmd_scope_aggregate(args: Any) -> None:
    try:
        plan = aggregate_scopes(os.path.abspath(args.dir), args.node, args.round,
                                scope_id=getattr(args, "scope_id", None))
    except (ScopeError, OSError, ValueError) as exc:
        _scope_error(exc)
    print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))


def cmd_scope_promote(args: Any) -> None:
    try:
        plan = promote_scopes(os.path.abspath(args.dir), args.node, args.round,
                              scope_id=getattr(args, "scope_id", None))
    except (ScopeError, OSError, ValueError) as exc:
        _scope_error(exc)
    print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))


__all__ = [
    "ScopeError", "SCOPED_NODES", "CODE_NODES", "COMMON_PHASES", "PAPER_PHASES", "REQUIRED_PHASES", "ALL_PHASES", "required_phases_for",
    "safe_scope_id", "safe_repo_relative", "discover_scopes", "plan_scopes",
    "update_scope_phase", "write_scope_report", "record_empty_return", "aggregate_scopes", "promote_scopes", "cmd_scope_plan",
    "cmd_scope_aggregate", "cmd_scope_promote", "utc_now",
]
