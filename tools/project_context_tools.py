"""Deterministic, read-only lookup against the bundled Demo project catalog."""

import json
import os
import re
from pathlib import Path

from pydantic import ValidationError

from schemas.panel_schema import PanelRequest
from schemas.project_context_schema import (
    DemoProjectCatalog,
    ObjectMatchResult,
    ObjectRole,
    ProjectInspectionResult,
)
from tools.ruler_plane_tools import normalize_ruler_plane_name


DEFAULT_DEMO_PROJECT_PATH = (
    Path(__file__).resolve().parents[1] / "mock_data" / "demo_project.json"
)


class ProjectContextError(RuntimeError):
    def __init__(self, message: str, *, error_code: str) -> None:
        super().__init__(message)
        self.error_code = error_code


def load_demo_project_catalog(
    path: Path | None = None,
) -> DemoProjectCatalog:
    configured_path = os.environ.get("DEMO_PROJECT_PATH")
    catalog_path = path or (
        Path(configured_path) if configured_path else DEFAULT_DEMO_PROJECT_PATH
    )
    try:
        raw = catalog_path.read_text(encoding="utf-8")
        return DemoProjectCatalog.model_validate_json(raw)
    except OSError as exc:
        raise ProjectContextError(
            "Mock 工程目录不可用。",
            error_code="PROJECT_CONTEXT_LOAD_ERROR",
        ) from exc
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        raise ProjectContextError(
            "Mock 工程目录格式无效。",
            error_code="PROJECT_CONTEXT_INVALID",
        ) from exc


def resolve_demo_object(
    query: str,
    *,
    role: ObjectRole,
    catalog: DemoProjectCatalog,
) -> ObjectMatchResult:
    normalized_query = _normalize_lookup_text(query)
    matches = [
        item
        for item in catalog.objects
        if normalized_query
        in {_normalize_lookup_text(item.name), *map(_normalize_lookup_text, item.aliases)}
    ]

    if not matches:
        return ObjectMatchResult(query=query, role=role, status="not_found")
    if len(matches) > 1:
        return ObjectMatchResult(
            query=query,
            role=role,
            status="ambiguous",
            candidates=[item.name for item in matches],
        )

    match = matches[0]
    if match.status != "available":
        return ObjectMatchResult(
            query=query,
            role=role,
            status="unavailable",
            candidates=[match.name],
        )
    if role not in match.eligible_roles:
        return ObjectMatchResult(
            query=query,
            role=role,
            status="not_eligible",
            candidates=[match.name],
        )
    return ObjectMatchResult(
        query=query,
        role=role,
        status="resolved",
        resolved_object_id=match.object_id,
        resolved_name=match.name,
    )


def inspect_project_context(
    panel: PanelRequest,
    *,
    catalog: DemoProjectCatalog | None = None,
) -> ProjectInspectionResult:
    project = catalog or load_demo_project_catalog()
    return ProjectInspectionResult(
        project_id=project.project_id,
        project_name=project.project_name,
        revision=project.revision,
        data_source="mock",
        reference_plane=resolve_demo_object(
            panel.reference_plane,
            role="reference_plane",
            catalog=project,
        ),
        boundaries=[
            resolve_demo_object(item.target, role="boundary", catalog=project)
            for item in panel.boundaries
        ],
    )


def extract_demo_reference_query(user_input: str) -> str | None:
    """Recover one explicit project query from non-boundary source text.

    Catalog names/aliases cover Demo surfaces such as ``主甲板``. A ruler-like
    token is also preserved even when it is absent from the catalog so the
    provider can return a visible ``not_found`` result (for example ``FR999``).
    """

    try:
        catalog = load_demo_project_catalog()
    except ProjectContextError:
        return None

    normalized_input = _normalize_lookup_text(user_input)
    matched_phrases: dict[str, str] = {}
    for item in catalog.objects:
        if "reference_plane" not in item.eligible_roles:
            continue
        for phrase in (item.name, *item.aliases):
            normalized = _normalize_lookup_text(phrase)
            if normalized and normalized in normalized_input:
                matched_phrases.setdefault(normalized, phrase)

    if matched_phrases:
        longest_length = max(len(value) for value in matched_phrases)
        longest = [
            phrase for normalized, phrase in matched_phrases.items()
            if len(normalized) == longest_length
        ]
        if len(longest) == 1:
            return longest[0]

    ruler_tokens = {
        re.sub(r"\s+", "", match.group(0)).upper()
        for match in re.finditer(r"(?<![A-Za-z0-9])(?:FR|SL|LV)\s*[+-]?\d+", user_input, re.I)
    }
    return next(iter(ruler_tokens)) if len(ruler_tokens) == 1 else None


def _normalize_lookup_text(value: str) -> str:
    ruler_name = normalize_ruler_plane_name(value.strip())
    return re.sub(r"\s+", "", ruler_name).casefold()
