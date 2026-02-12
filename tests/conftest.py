"""Pytest fixtures for integration tests: mock OneNote gateway and combined MCP app."""

import pytest

from onenote_mcp.domain.models import Notebook, Page, Section
from onenote_mcp.domain.ports import OneNoteGateway


class MockOneNoteGateway(OneNoteGateway):
    """In-memory gateway that returns fixed data for tests (no Microsoft Graph)."""

    def __init__(self, **kwargs) -> None:
        """Accept and ignore Graph client kwargs (tenant_id, client_id, etc.)."""
        self.notebooks = [
            Notebook(
                id="nb-1",
                display_name="Test Notebook",
                self_url="https://graph.microsoft.com/.../notebooks/nb-1",
                sections_url="https://graph.microsoft.com/.../notebooks/nb-1/sections",
                created_date_time="2024-01-01T00:00:00Z",
                last_modified_date_time="2024-01-02T00:00:00Z",
            ),
        ]
        self.sections = [
            Section(
                id="sec-1",
                display_name="Test Section",
                self_url="https://graph.microsoft.com/.../sections/sec-1",
                pages_url="https://graph.microsoft.com/.../sections/sec-1/pages",
                created_date_time="2024-01-01T00:00:00Z",
                last_modified_date_time="2024-01-02T00:00:00Z",
                notebook_id="nb-1",
            ),
        ]
        self.pages = [
            Page(
                id="page-1",
                title="My First Note",
                content_url="https://graph.microsoft.com/.../pages/page-1/content",
                self_url="https://graph.microsoft.com/.../pages/page-1",
                created_date_time="2024-01-01T00:00:00Z",
                last_modified_date_time="2024-01-02T00:00:00Z",
                section_id="sec-1",
                notebook_id="nb-1",
            ),
        ]
        self.page_content: dict[str, str] = {
            "page-1": "<html><body><p>Hello from the note.</p></body></html>",
        }

    async def list_notebooks(self, user_id: str | None = None) -> list[Notebook]:
        return list(self.notebooks)

    async def list_sections(
        self,
        notebook_id: str,
        user_id: str | None = None,
    ) -> list[Section]:
        return [s for s in self.sections if s.notebook_id == notebook_id]

    async def list_pages(
        self,
        section_id: str | None = None,
        notebook_id: str | None = None,
        user_id: str | None = None,
    ) -> list[Page]:
        if section_id:
            return [p for p in self.pages if p.section_id == section_id]
        return list(self.pages)

    async def get_page_content(
        self,
        page_id: str,
        user_id: str | None = None,
    ) -> str:
        return self.page_content.get(page_id, "")


@pytest.fixture
def mock_gateway() -> MockOneNoteGateway:
    """Return a mock OneNote gateway with fixed test data."""
    return MockOneNoteGateway()


@pytest.fixture
def app(mock_gateway: MockOneNoteGateway):
    """Build the combined MCP app (SSE + Streamable HTTP) with the mock gateway injected.
    Patch stays active for the whole test so the MCP server uses the mock gateway at runtime.
    """
    from unittest.mock import MagicMock, patch

    with patch("onenote_mcp.server.GraphOneNoteGateway", MagicMock(return_value=mock_gateway)):
        from onenote_mcp.main import get_combined_app

        yield get_combined_app()


