"""Replay user-authored boundary edits; never use model-invented expressions."""

import re

from schemas.boundary_schema import BoundaryParseResult, BoundaryValidationIssue
from tools.boundary_tools import parse_boundary_expressions


_TURN = re.compile(r"(?:\A初始需求[:：]|\n用户第\d+次补充[:：])")
_FIELD = re.compile(r"(?:定位面|厚度|材料)(?:为|是|[:：]|\s|(?=[A-Za-z0-9]))")
_QUOTES = {'"': '"', "'": "'", "“": "”", "‘": "’"}


def _outside_positions(text: str):
    closing = None
    for index, char in enumerate(text):
        if closing:
            if char == closing:
                closing = None
        elif char in _QUOTES:
            closing = _QUOTES[char]
        else:
            yield index


def boundary_text(turn: str) -> str | None:
    """Extract one boundary clause, retaining invalid fragments for clarification."""
    positions = list(_outside_positions(turn))
    label = next((i for i in positions if turn.startswith('边界', i)), None)
    signed = next((i for i in positions if turn[i] in '<>＜＞'), None)
    if label is None and signed is None:
        return None
    start = label + 2 if label is not None else signed
    edit_prefix = re.match(r'\s*(?:将|把)\s*', turn)
    if label is None and edit_prefix:
        start = edit_prefix.end()
    if label is not None:
        prefix = re.match(r'\s*(?:为|是|追加|再加|补充)?\s*[:：]?', turn[start:])
        start += prefix.end()
    end = len(turn)
    for i in positions:
        if i <= start:
            continue
        if turn[i] == '。' or (turn[i - 1] in ',，;； \n' and _FIELD.match(turn, i)):
            end = i
            break
    source = turn[start:end].strip(' \t\r\n,，;；。')
    # A later boundary clause must not disappear just because a scalar field
    # or sentence ended the first clause (including later malformed input).
    if end < len(turn):
        remainder = boundary_text(turn[end + 1:] if turn[end] == '。' else turn[end:])
        if remainder is not None:
            source += '; ' + remainder
    return source


def resolve_boundary_session(user_input: str) -> BoundaryParseResult:
    fragments: list[str] = []
    edit_issue = None
    for turn in (part for part in _TURN.split(user_input) if part.strip()):
        source = boundary_text(turn)
        if source is None:
            continue
        # Explicit whole-list replacement takes precedence over single-item edits.
        outside = set(_outside_positions(turn))
        whole = next((match for match in re.finditer(
            r'边界\s*(?:全部|全都|整体)\s*(?:改为|替换为|换成)', turn
        ) if match.start() in outside), None)
        if whole:
            source = boundary_text('边界 ' + turn[whole.end():])
            fragments = [item.raw for item in parse_boundary_expressions(source or '').candidates]
            edit_issue = None
            continue
        replacement = next((i for i in _outside_positions(source)
                            if source.startswith('改为', i) or source.startswith('替换为', i)), None)
        if replacement is not None:
            old = source[:replacement].strip()
            keyword = '替换为' if source.startswith('替换为', replacement) else '改为'
            new = source[replacement + len(keyword):].strip()
            old_result = parse_boundary_expressions(old)
            new_result = parse_boundary_expressions(new)
            matches = []
            for i, raw in enumerate(fragments):
                parsed = parse_boundary_expressions(raw)
                if raw.strip() == old or (not old_result.issues and not parsed.issues
                                         and old_result.boundaries == parsed.boundaries):
                    matches.append(i)
            if len(matches) == 1 and len(new_result.candidates) == 1 and not new_result.issues:
                fragments[matches[0]] = new_result.candidates[0].raw
                edit_issue = None
            else:
                edit_issue = '无法唯一确定要替换的边界或新边界不合法，请使用“边界全部改为 …”。'
            continue
        parsed = parse_boundary_expressions(source)
        incoming = [item.raw for item in parsed.candidates]
        append = any(match.start() in outside for match in re.finditer(r'(?:再加|追加|补充)', turn))
        if not fragments or append:
            fragments.extend(incoming)
            edit_issue = None
        else:
            edit_issue = '已有边界，请明确使用“追加边界 …”或“边界全部改为 …”。'
    result = parse_boundary_expressions('; '.join(fragments))
    if edit_issue:
        result.issues.append(BoundaryValidationIssue(
            code='BOUNDARY_EDIT_AMBIGUOUS', message=edit_issue,
        ))
    return result


def recover_missing_scalars(data: dict, reference_text: str) -> None:
    """Recover unambiguous user values omitted by the model during a follow-up.

    Only source-backed numeric thickness and explicitly named material are used.
    Multiple distinct values are left for clarification rather than guessed.
    """
    if not _TURN.search(reference_text):
        return
    if data.get('thickness') is None:
        values = set(re.findall(r'厚度\s*(?:为|是|改为)?\s*[:：]?\s*([+-]?\d+(?:\.\d+)?)\s*(?:mm|毫米)', reference_text, re.I))
        values.update(re.findall(r'(?<![A-Za-z0-9_.])([+-]?\d+(?:\.\d+)?)\s*(?:mm|毫米)\s*厚', reference_text, re.I))
        if len(values) == 1:
            data['thickness'] = float(next(iter(values)))
    if not data.get('material'):
        values = set(re.findall(r'材料\s*(?:为|是|改为|换成|修改为)?\s*[:：]?\s*([A-Za-z][A-Za-z0-9_-]*)', reference_text))
        values.update(re.findall(r'厚\s*([A-Za-z][A-Za-z0-9_-]*)\s*(?:的)?板架', reference_text))
        if len(values) == 1:
            data['material'] = next(iter(values))
