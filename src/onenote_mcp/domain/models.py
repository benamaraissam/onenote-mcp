"""Domain models for OneNote entities."""

from dataclasses import dataclass
from typing import Any


def _get(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Get value from dict with optional camelCase/snake_case keys."""
    for k in keys:
        if k in data and data[k] is not None:
            return data[k]
    return default


@dataclass(frozen=True)
class Notebook:
    """A OneNote notebook."""

    id: str
    display_name: str
    self_url: str
    sections_url: str
    created_date_time: str | None
    last_modified_date_time: str | None

    @classmethod
    def from_graph(cls, data: dict[str, Any]) -> "Notebook":
        return cls(
            id=data["id"],
            display_name=_get(data, "display_name", "displayName") or "",
            self_url=_get(data, "self_url", "self") or "",
            sections_url=_get(data, "sections_url", "sections_url") or "",
            created_date_time=_get(data, "created_date_time", "created_date_time"),
            last_modified_date_time=_get(data, "last_modified_date_time", "last_modified_date_time"),
        )


@dataclass(frozen=True)
class Section:
    """A OneNote section within a notebook."""

    id: str
    display_name: str
    self_url: str
    pages_url: str
    created_date_time: str | None
    last_modified_date_time: str | None
    notebook_id: str | None = None

    @classmethod
    def from_graph(cls, data: dict[str, Any], notebook_id: str | None = None) -> "Section":
        return cls(
            id=data["id"],
            display_name=_get(data, "display_name", "displayName") or "",
            self_url=_get(data, "self_url", "self") or "",
            pages_url=_get(data, "pages_url", "pagesUrl") or "",
            created_date_time=_get(data, "created_date_time", "created_date_time"),
            last_modified_date_time=_get(data, "last_modified_date_time", "last_modified_date_time"),
            notebook_id=notebook_id,
        )


@dataclass(frozen=True)
class Page:
    """A OneNote page (note)."""

    id: str
    title: str
    content_url: str
    self_url: str
    created_date_time: str | None
    last_modified_date_time: str | None
    section_id: str | None = None
    notebook_id: str | None = None

    @classmethod
    def from_graph(
        cls,
        data: dict[str, Any],
        section_id: str | None = None,
        notebook_id: str | None = None,
    ) -> "Page":
        return cls(
            id=data["id"],
            title=_get(data, "title") or "",
            content_url=_get(data, "content_url", "content_url") or "",
            self_url=_get(data, "self_url", "self") or "",
            created_date_time=_get(data, "created_date_time", "created_date_time"),
            last_modified_date_time=_get(data, "last_modified_date_time", "last_modified_date_time"),
            section_id=section_id,
            notebook_id=notebook_id,
        )
