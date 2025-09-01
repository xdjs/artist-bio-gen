"""
Text processing utilities.

Provides helpers for cleaning OpenAI response text, including removing
trailing citation/link blocks while preserving legitimate content.
"""

from __future__ import annotations

import re


_MD_LINK = r"\[[^\]]+\]\([^\)]+\)"  # [text](url)
_RAW_URL = r"https?://[^\s)]+"          # bare URL (no closing paren)
_LINK_TOKEN = rf"(?:{_MD_LINK}|{_RAW_URL})"


def strip_trailing_citations(text: str) -> str:
    """
    Strip trailing citation/link blocks from the end of a generated bio.

    Rules:
    - Remove a final parenthetical that contains only links/URLs, separated by commas.
    - Or remove a trailing "Sources:"/"References:" block containing only links/URLs.
    - Preserve mid-text links and any non-citation parentheses.
    - Be idempotent: applying multiple times yields the same result.
    """
    if not text:
        return text

    s = text.rstrip()

    # Pattern 1: trailing Sources/References line with only links
    # Optional leading whitespace, optional preceding dash/em dash, then label and links to end.
    sources_pattern = re.compile(
        rf"(?is)"  # case-insensitive, dot matches newline
        rf"(?:[ \t]*[\r\n]+|[ \t]{{2,}}|[—–-]\s*)?"  # preceding whitespace/newline or dash
        rf"(?:sources?|references?)\s*:\s*"
        rf"{_LINK_TOKEN}(?:\s*[,·|]\s*{_LINK_TOKEN})*\s*$",
        re.IGNORECASE,
    )

    s2 = sources_pattern.sub("", s)
    if s2 != s:
        return s2.rstrip(" \t\r\n—–-|·,")

    # Pattern 2: trailing parenthetical with only links separated by commas
    paren_links_pattern = re.compile(
        rf"\s*\(\s*{_LINK_TOKEN}(?:\s*,\s*{_LINK_TOKEN})*\s*\)\s*$"
    )

    s2 = paren_links_pattern.sub("", s)
    if s2 != s:
        return s2.rstrip(" \t\r\n—–-|·,")

    return s

