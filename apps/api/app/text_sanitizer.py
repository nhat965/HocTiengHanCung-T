from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, String, Text
from sqlalchemy.types import TypeDecorator


def sanitize_text(value: str) -> str:
    return value.replace("\x00", "\uFFFD")


def sanitize_json(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, list):
        return [sanitize_json(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_json(item) for item in value)
    if isinstance(value, dict):
        return {sanitize_text(key) if isinstance(key, str) else key: sanitize_json(item) for key, item in value.items()}
    return value


class SanitizedString(TypeDecorator[str]):
    impl = String
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect) -> str | None:
        return sanitize_text(value) if value is not None else None


class SanitizedText(TypeDecorator[str]):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect) -> str | None:
        return sanitize_text(value) if value is not None else None


class SanitizedJSON(TypeDecorator[Any]):
    impl = JSON
    cache_ok = True

    def process_bind_param(self, value: Any, dialect) -> Any:
        return sanitize_json(value)
