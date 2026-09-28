"""Подсистема кроссбраузерного управления и антидетекта через WebDriver BiDi."""

from __future__ import annotations

from chutils.scraping.bidi.antidetect import apply_antidetect_bidi
from chutils.scraping.bidi.client import BiDiClient
from chutils.scraping.bidi.exceptions import (
    BiDiCommandError,
    BiDiConnectionError,
    BiDiError,
    BiDiTimeoutError,
)
from chutils.scraping.bidi.session import BiDiSession, bidi_session, extract_bidi_url

__all__ = [
    "BiDiClient",
    "BiDiCommandError",
    "BiDiConnectionError",
    "BiDiError",
    "BiDiSession",
    "BiDiTimeoutError",
    "apply_antidetect_bidi",
    "bidi_session",
    "extract_bidi_url",
]
