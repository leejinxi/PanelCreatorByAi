import re
from collections.abc import Sequence

from schemas.reference_plane_schema import (
    PlaneByCoordinate,
    PlaneByDescription,
    PlaneByName,
    ReferencePlaneRecord,
    ReferencePlaneResolution,
    ReferencePlaneSelector,
)


COORDINATE_VALUE_PATTERN = r"[+-]?\d+(?:\.\d+)?"
UNIT_PATTERN = r"mm|cm|m|毫米|厘米|米"


def list_reference_planes() -> list[ReferencePlaneRecord]:
    """返回当前工程的标尺面目录。

    当前为 Mock CAD 数据。接入 MCP 后，只需把本函数替换为对当前
    CAD 工程的实时查询，名称解析逻辑不需要修改。
    """

    return [
        ReferencePlaneRecord(
            object_id="mock-plane-fr100",
            name="FR100",
            aliases=["FR 100", "第100肋位", "100号肋位"],
            axis="X",
            coordinate_mm=10000,
        ),
        ReferencePlaneRecord(
            object_id="mock-plane-surface-20",
            name="SURFACE_20",
            aliases=["SURFACE 20", "20号曲面"],
        ),
        ReferencePlaneRecord(
            object_id="mock-plane-centerline",
            name="CENTERLINE",
            aliases=["中心纵剖面", "中纵面"],
            axis="Y",
            coordinate_mm=0,
        ),
    ]


def normalize_plane_text(value: str) -> str:
    """用于工程名称匹配的轻量归一化，不改变保存到 CAD 的真实名称。"""

    return re.sub(r"[\s_\-]+", "", value).casefold()


def extract_coordinate_selector(
    user_input: str,
    planes: Sequence[ReferencePlaneRecord],
) -> PlaneByCoordinate | None:
    """从用户输入中提取工程目录支持的轴向坐标表达式。"""

    catalog_axes = {
        plane.axis
        for plane in planes
        if plane.axis is not None
    }
    axes = sorted(catalog_axes | {"X", "Y", "Z"}, key=len, reverse=True)
    if not axes:
        return None

    axis_pattern = "|".join(re.escape(axis) for axis in axes)
    pattern = re.compile(
        rf"(?<![A-Za-z0-9_])(?P<axis>{axis_pattern})"
        rf"\s*=\s*(?P<value>{COORDINATE_VALUE_PATTERN})"
        rf"\s*(?P<unit>{UNIT_PATTERN})?",
        re.IGNORECASE,
    )
    match = pattern.search(user_input)
    if match is None:
        return None

    return PlaneByCoordinate(
        axis=match.group("axis"),
        value=float(match.group("value")),
        unit=_normalize_unit(match.group("unit")),
    )


def extract_catalog_name_selector(
    user_input: str,
    planes: Sequence[ReferencePlaneRecord],
) -> PlaneByName | None:
    """从原始输入中直接查找当前工程已知名称或别名。"""

    normalized_input = normalize_plane_text(user_input)
    matches: list[tuple[int, str]] = []

    for plane in planes:
        for candidate in [plane.name, *plane.aliases]:
            normalized_candidate = normalize_plane_text(candidate)
            if normalized_candidate and normalized_candidate in normalized_input:
                matches.append((len(normalized_candidate), candidate))

    if not matches:
        return None

    # 优先使用最长匹配，防止短别名覆盖更具体的工程名称。
    matches.sort(key=lambda item: item[0], reverse=True)
    return PlaneByName(name=matches[0][1])


def resolve_reference_plane(
    *,
    user_input: str,
    planes: Sequence[ReferencePlaneRecord],
    llm_reference: str | None = None,
    tolerance_mm: float = 0.1,
) -> ReferencePlaneResolution:
    """综合坐标、工程名称/别名和 LLM 结果解析真实定位面。"""

    coordinate_selector = extract_coordinate_selector(user_input, planes)
    name_selector = extract_catalog_name_selector(user_input, planes)

    if coordinate_selector is not None and name_selector is not None:
        coordinate_matches = _match_by_coordinate(
            coordinate_selector,
            planes,
            tolerance_mm,
        )
        name_matches = _match_by_name(name_selector.name, planes)
        shared = _intersection_by_object_id(coordinate_matches, name_matches)

        if len(shared) == 1:
            return _resolved(coordinate_selector, shared[0])

        return ReferencePlaneResolution(
            status="conflict",
            selector=coordinate_selector,
            candidates=_unique_planes([*coordinate_matches, *name_matches]),
            message="输入中的定位面名称与坐标不能解析为同一个工程标尺面。",
        )

    if coordinate_selector is not None:
        return _resolution_from_matches(
            coordinate_selector,
            _match_by_coordinate(coordinate_selector, planes, tolerance_mm),
            "当前工程中没有匹配该坐标的标尺面。",
        )

    if name_selector is not None:
        return _resolution_from_matches(
            name_selector,
            _match_by_name(name_selector.name, planes),
            "当前工程中没有匹配该名称的标尺面。",
        )

    if llm_reference and llm_reference.strip():
        description_selector = PlaneByDescription(text=llm_reference)
        return _resolution_from_matches(
            description_selector,
            _match_by_name(llm_reference, planes),
            f"当前工程中不存在定位面“{llm_reference.strip()}”。",
        )

    return ReferencePlaneResolution(
        status="not_found",
        message="没有从用户输入中识别出定位面。",
    )


def _match_by_name(
    query: str,
    planes: Sequence[ReferencePlaneRecord],
) -> list[ReferencePlaneRecord]:
    normalized_query = normalize_plane_text(query)
    matches = []

    for plane in planes:
        candidates = [plane.name, *plane.aliases]
        if any(
            normalize_plane_text(candidate) == normalized_query
            for candidate in candidates
        ):
            matches.append(plane)

    return _unique_planes(matches)


def _match_by_coordinate(
    selector: PlaneByCoordinate,
    planes: Sequence[ReferencePlaneRecord],
    tolerance_mm: float,
) -> list[ReferencePlaneRecord]:
    target_mm = _to_mm(selector.value, selector.unit)

    return [
        plane
        for plane in planes
        if plane.axis == selector.axis
        and plane.coordinate_mm is not None
        and abs(plane.coordinate_mm - target_mm) <= tolerance_mm
        and (
            selector.coordinate_system is None
            or plane.coordinate_system == selector.coordinate_system
        )
    ]


def _resolution_from_matches(
    selector: ReferencePlaneSelector,
    matches: list[ReferencePlaneRecord],
    not_found_message: str,
) -> ReferencePlaneResolution:
    if len(matches) == 1:
        return _resolved(selector, matches[0])

    if len(matches) > 1:
        return ReferencePlaneResolution(
            status="ambiguous",
            selector=selector,
            candidates=matches,
            message="匹配到多个定位面，需要用户选择。",
        )

    return ReferencePlaneResolution(
        status="not_found",
        selector=selector,
        message=not_found_message,
    )


def _resolved(
    selector: ReferencePlaneSelector,
    plane: ReferencePlaneRecord,
) -> ReferencePlaneResolution:
    return ReferencePlaneResolution(
        status="resolved",
        selector=selector,
        resolved=plane,
    )


def _intersection_by_object_id(
    left: Sequence[ReferencePlaneRecord],
    right: Sequence[ReferencePlaneRecord],
) -> list[ReferencePlaneRecord]:
    right_ids = {plane.object_id for plane in right}
    return [plane for plane in left if plane.object_id in right_ids]


def _unique_planes(
    planes: Sequence[ReferencePlaneRecord],
) -> list[ReferencePlaneRecord]:
    result = []
    seen_ids = set()

    for plane in planes:
        if plane.object_id not in seen_ids:
            result.append(plane)
            seen_ids.add(plane.object_id)

    return result


def _normalize_unit(unit: str | None) -> str:
    unit_mapping = {
        None: "mm",
        "mm": "mm",
        "毫米": "mm",
        "cm": "cm",
        "厘米": "cm",
        "m": "m",
        "米": "m",
    }
    return unit_mapping[unit.lower() if unit is not None else None]


def _to_mm(value: float, unit: str) -> float:
    factors = {
        "mm": 1.0,
        "cm": 10.0,
        "m": 1000.0,
    }
    return value * factors[unit]
