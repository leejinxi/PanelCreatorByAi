"""Deterministic boundary syntax. Operators are opaque; no geometry is inferred.

parse_boundary_expressions accepts boundary text only, not a whole conversation.
Every non-separator fragment is retained; malformed fragments block execution.
Offsets refer to the original text, including full-width operator characters.
"""

import re

from schemas.boundary_schema import (
    BoundaryCandidate, BoundaryConstraint, BoundaryParseResult,
    BoundaryValidationIssue,
)


_OPERATORS = "<>＜＞"
_SYMBOLS = _OPERATORS + "=＝"
_SEPARATORS = " \t\r\n,，;；"
_QUOTES = {'"': '"', "'": "'", "“": "”", "‘": "’"}
_RULER_TARGET = re.compile(
    r"(?:FR|SL|LV)[ \t]*[+-]?\d+|(?:第[ \t]*)?[+-]?\d+[ \t]*(?:号[ \t]*)?肋位",
    re.IGNORECASE,
)


def _target_end(text: str, start: int) -> tuple[int, str, str | None]:
    """Consume one whole target, including malformed quoted/suffixed targets."""
    if text[start] in _QUOTES:
        close = _QUOTES[text[start]]
        end = text.find(close, start + 1)
        if end < 0:
            return len(text), text[start + 1:], "BOUNDARY_QUOTE_INVALID"
        target = text[start + 1:end]
        end += 1
        if end < len(text) and text[end] not in _SEPARATORS + _OPERATORS:
            while end < len(text) and text[end] not in _SEPARATORS:
                end += 1
            return end, target, "BOUNDARY_TARGET_INVALID"
        return end, target, None

    match = _RULER_TARGET.match(text, start)
    if match and (match.end() == len(text) or text[match.end()] in _SEPARATORS + _OPERATORS):
        return match.end(), match.group(), None
    end = start
    while end < len(text) and text[end] not in _SEPARATORS + _OPERATORS:
        end += 1
    target = text[start:end]
    invalid = any(char in target for char in '"\'“”‘’')
    return end, target, "BOUNDARY_QUOTE_INVALID" if invalid else None


def parse_boundary_expressions(text: str) -> BoundaryParseResult:
    result = BoundaryParseResult()
    cursor = 0
    seen: set[BoundaryConstraint] = set()
    while cursor < len(text):
        if text[cursor] in _SEPARATORS:
            cursor += 1
            continue
        start = cursor
        operator = None
        code = None
        if text[cursor] in _SYMBOLS:
            while cursor < len(text) and text[cursor] in _SYMBOLS:
                cursor += 1
            operator = text[start:cursor].translate(str.maketrans("＜＞", "<>"))
            if operator not in ("<", ">"):
                code = "BOUNDARY_OPERATOR_INVALID"
            while cursor < len(text) and text[cursor] in " \t":
                cursor += 1
            if cursor < len(text) and text[cursor] in "=＝":
                code = "BOUNDARY_OPERATOR_INVALID"
        else:
            code = "BOUNDARY_OPERATOR_MISSING"

        target = None
        if cursor == len(text) or text[cursor] in _SEPARATORS + _OPERATORS:
            code = code or "BOUNDARY_TARGET_MISSING"
        else:
            cursor, target, target_code = _target_end(text, cursor)
            code = code or target_code
            if not target.strip():
                code = code or "BOUNDARY_TARGET_MISSING"
        index = len(result.candidates)
        result.candidates.append(BoundaryCandidate(
            raw=text[start:cursor], start=start, end=cursor,
            operator=operator, target=target,
        ))
        if code:
            messages = {
                "BOUNDARY_OPERATOR_MISSING": "边界缺少 < 或 > 符号",
                "BOUNDARY_OPERATOR_INVALID": "边界符号只能是单个 < 或 >",
                "BOUNDARY_TARGET_MISSING": "边界缺少目标名称",
                "BOUNDARY_QUOTE_INVALID": "目标名称的引号不完整或位置不正确",
                "BOUNDARY_TARGET_INVALID": "带引号的目标后存在未识别内容",
            }
            result.issues.append(BoundaryValidationIssue(
                code=code, index=index, message=messages[code],
            ))
            continue
        boundary = BoundaryConstraint(operator=operator, target=target)
        if boundary in seen:
            result.duplicate_indices.append(index)
        else:
            seen.add(boundary)
            result.boundaries.append(boundary)
    if not result.boundaries:
        result.issues.append(BoundaryValidationIssue(
            code="BOUNDARY_COUNT_INSUFFICIENT",
            message="已收到0条有效边界，还需至少1条",
        ))
    return result


def mask_boundary_text(text: str) -> str:
    """Exclude boundary roles before reference-plane extraction, keeping offsets.

    Explicit boundary clauses end at a sentence, turn marker or explicit field.
    Unlabelled signed expressions are also excluded. Ambiguous free prose is
    masked conservatively so it cannot silently supply a reference plane.
    """
    chars = list(text)
    field_start = re.compile(
        r"(?:定位面|厚度|材料)(?:为|是|[:：]|\s|(?=[A-Za-z0-9]))|(?:初始需求|用户第\d+次补充)[:：]"
    )
    cursor = 0
    while cursor < len(text):
        # Field names inside quoted boundary targets cannot end a clause.
        if text[cursor] in _QUOTES:
            cursor, _, _ = _target_end(text, cursor)
            continue
        if not text.startswith("边界", cursor):
            cursor += 1
            continue
        start = cursor
        cursor += 2
        while cursor < len(text) and text[cursor] != "。":
            if text[cursor - 1] in _SEPARATORS and field_start.match(text, cursor):
                break
            if text[cursor] in _QUOTES:
                cursor, _, _ = _target_end(text, cursor)
            else:
                cursor += 1
        chars[start:cursor] = " " * (cursor - start)
    remaining = "".join(chars)
    cursor = 0
    while cursor < len(remaining):
        if remaining[cursor] not in _OPERATORS:
            cursor += 1
            continue
        start = cursor
        while cursor < len(remaining) and remaining[cursor] in _SYMBOLS + " \t":
            cursor += 1
        if cursor < len(remaining) and remaining[cursor] not in _SEPARATORS:
            cursor, _, _ = _target_end(remaining, cursor)
        chars[start:cursor] = " " * (cursor - start)
    return "".join(chars)
