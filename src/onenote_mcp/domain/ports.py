"""Ports (interfaces) for OneNote access — infrastructure implements these."""

from abc import ABC, abstractmethod
from typing import Any

from onenote_mcp.domain.models import Notebook, Page, Section


class OneNoteGateway(ABC):
    """Abstract gateway to OneNote (Microsoft Graph)."""

    @abstractmethod
    async def list_notebooks(self, user_id: str | None = None) -> list[Notebook]:
        """List all notebooks for the user (or for the given user_id in app-only auth)."""
        ...

    @abstractmethod
    async def list_sections(
        self,
        notebook_id: str,
        user_id: str | None = None,
    ) -> list[Section]:
        """List all sections in a notebook."""
        ...

    @abstractmethod
    async def list_pages(
        self,
        section_id: str | None = None,
        notebook_id: str | None = None,
        user_id: str | None = None,
    ) -> list[Page]:
        """List pages: either in a section, in a notebook, or all pages for the user."""
        ...

    @abstractmethod
    async def get_page_content(
        self,
        page_id: str,
        user_id: str | None = None,
    ) -> str:
        """Get the HTML content of a page."""
        ...
