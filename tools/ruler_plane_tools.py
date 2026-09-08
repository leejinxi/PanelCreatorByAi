import re


RULER_PLANE_RANGES: dict[str, tuple[int, int]] = {
    "FR": (-10, 200),
    "SL": (-40, 40),
    "LV": (-5, 50),
}

_CANONICAL_PLANE_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])(?P<prefix>FR|SL|LV)\s*"
    r"(?P<index>[+-]?\d+)(?![A-Za-z0-9_])",
    re.IGNORECASE,
)
_CHINESE_FRAME_PATTERN = re.compile(
    r"(?:第\s*)?(?P<index>[+-]?\d+)\s*(?:号\s*)?肋位",
)


def normalize_ruler_plane_name(value: str) -> str:
    """把已知标尺面写法转换为 CAD 使用的标准名称。"""

    normalized = value.strip()

    canonical_match = _CANONICAL_PLANE_PATTERN.fullmatch(normalized)
    if canonical_match is not None:
        return _canonical_name_if_known(
            canonical_match.group("prefix"),
            int(canonical_match.group("index")),
        ) or normalized

    frame_match = _CHINESE_FRAME_PATTERN.fullmatch(normalized)
    if frame_match is not None:
        return _canonical_name_if_known(
            "FR",
            int(frame_match.group("index")),
        ) or normalized

    return normalized


def extract_known_ruler_plane_name(user_input: str) -> str | None:
    """从用户原文提取唯一的已知标尺面；多值或未找到时返回 None。"""

    matches: list[str] = []

    for match in _CANONICAL_PLANE_PATTERN.finditer(user_input):
        name = _canonical_name_if_known(
            match.group("prefix"),
            int(match.group("index")),
        )
        if name is not None:
            matches.append(name)

    for match in _CHINESE_FRAME_PATTERN.finditer(user_input):
        name = _canonical_name_if_known(
            "FR",
            int(match.group("index")),
        )
        if name is not None:
            matches.append(name)

    unique_matches = list(dict.fromkeys(matches))
    return unique_matches[0] if len(unique_matches) == 1 else None


def _canonical_name_if_known(prefix: str, index: int) -> str | None:
    normalized_prefix = prefix.upper()
    minimum, maximum = RULER_PLANE_RANGES[normalized_prefix]
    if minimum <= index <= maximum:
        return f"{normalized_prefix}{index}"
    return None
