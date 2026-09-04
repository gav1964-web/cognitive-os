"""Bounded token-aware matching for human-language registry markers."""

from __future__ import annotations

import re
from dataclasses import dataclass


_TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)
_CYRILLIC_RE = re.compile(r"^[\u0430-\u044f]+$")


@dataclass(frozen=True)
class MarkerMatch:
    matched: bool
    strategy: str
    marker: str
    matched_tokens: tuple[str, ...] = ()


def match_marker(text: str, marker: str, *, max_gap: int = 2) -> MarkerMatch:
    """Match a registry marker exactly or as an ordered inflection-tolerant phrase.

    Single-token fuzzy matching is deliberately disabled: registry fragments such
    as ``нижн`` already work through substring matching, while fuzzy fragments
    would create overly broad routes.
    """

    normalized_text = _normalize(text)
    normalized_marker = _normalize(marker)
    if not normalized_marker:
        return MarkerMatch(False, "empty_marker", marker)
    if normalized_marker in normalized_text:
        return MarkerMatch(True, "substring", marker, tuple(_tokens(normalized_marker)))

    marker_tokens = _tokens(normalized_marker)
    if len(marker_tokens) < 2:
        return MarkerMatch(False, "no_match", marker)
    text_tokens = _tokens(normalized_text)
    positions = _ordered_positions(text_tokens, marker_tokens, max_gap=max_gap)
    if positions is None:
        return MarkerMatch(False, "no_match", marker)
    return MarkerMatch(
        True,
        "ordered_token_inflection",
        marker,
        tuple(text_tokens[position] for position in positions),
    )


def marker_matches(text: str, marker: str, *, max_gap: int = 2) -> bool:
    return match_marker(text, marker, max_gap=max_gap).matched


def _normalize(value: str) -> str:
    return " ".join(_tokens(value.casefold().replace("ё", "е")))


def _tokens(value: str) -> list[str]:
    return _TOKEN_RE.findall(value.casefold().replace("ё", "е"))


def _ordered_positions(text: list[str], marker: list[str], *, max_gap: int) -> list[int] | None:
    positions: list[int] = []
    cursor = 0
    previous = -1
    for expected in marker:
        limit = len(text) if previous < 0 else min(len(text), previous + max_gap + 2)
        position = next(
            (index for index in range(cursor, limit) if _tokens_equivalent(text[index], expected)),
            None,
        )
        if position is None:
            return None
        positions.append(position)
        previous = position
        cursor = position + 1
    return positions


def _tokens_equivalent(left: str, right: str) -> bool:
    if left == right:
        return True
    if not (_CYRILLIC_RE.fullmatch(left) and _CYRILLIC_RE.fullmatch(right)):
        return False
    shorter = min(len(left), len(right))
    if shorter < 5:
        return False
    common = 0
    for left_char, right_char in zip(left, right):
        if left_char != right_char:
            break
        common += 1
    return common >= max(4, shorter - 3)
