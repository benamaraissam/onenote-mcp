"""Integration tests: use cases with mock gateway, tool output shape, and app routes (no live HTTP)."""

import pytest

from onenote_mcp.application.use_cases import (
    get_note_content,
    list_notebooks,
    list_pages,
    list_sections,
)
from onenote_mcp.domain.models import Notebook, Page, Section
from tests.conftest import MockOneNoteGateway


# ---- Use case tests (mock gateway, no MCP/HTTP) ----


@pytest.mark.asyncio
async def test_list_notebooks_returns_mock_data():
    """Use case list_notebooks with mock gateway returns expected notebooks."""
    gateway = MockOneNoteGateway()
    notebooks = await list_notebooks(gateway)
    assert len(notebooks) == 1
    assert notebooks[0].display_name == "Test Notebook"
    assert notebooks[0].id == "nb-1"


@pytest.mark.asyncio
async def test_list_sections_returns_mock_data():
    """Use case list_sections with mock gateway returns expected sections."""
    gateway = MockOneNoteGateway()
    sections = await list_sections(gateway, notebook_id="nb-1")
    assert len(sections) == 1
    assert sections[0].display_name == "Test Section"
    assert sections[0].id == "sec-1"


@pytest.mark.asyncio
async def test_list_pages_returns_mock_data():
    """Use case list_pages with mock gateway returns expected pages."""
    gateway = MockOneNoteGateway()
    pages = await list_pages(gateway)
    assert len(pages) == 1
    assert pages[0].title == "My First Note"
    assert pages[0].id == "page-1"


@pytest.mark.asyncio
async def test_get_note_content_returns_mock_html():
    """Use case get_note_content with mock gateway returns expected HTML."""
    gateway = MockOneNoteGateway()
    content = await get_note_content(gateway, page_id="page-1")
    assert "Hello from the note" in content
    assert "<html>" in content or "<p>" in content


# ---- Tool output shape (server formats use-case results) ----


def _tool_list_notes_output(notebooks: list[Notebook]) -> str:
    """Replicate server tool formatting for list_notes."""
    if not notebooks:
        return "No notebooks found."
    return "\n".join(f"- **{n.display_name}** (id: `{n.id}`)" for n in notebooks)


def _tool_list_sections_output(sections: list[Section]) -> str:
    """Replicate server tool formatting for list_note_sections."""
    if not sections:
        return "No sections found in this notebook."
    return "\n".join(f"- **{s.display_name}** (id: `{s.id}`)" for s in sections)


def _tool_list_pages_output(pages: list[Page]) -> str:
    """Replicate server tool formatting for list_note_pages."""
    if not pages:
        return "No pages found."
    return "\n".join(f"- **{p.title or '(untitled)'}** (id: `{p.id}`)" for p in pages)


@pytest.mark.asyncio
async def test_tool_list_notes_output_format():
    """Tool list_notes output format matches expected markdown."""
    gateway = MockOneNoteGateway()
    notebooks = await list_notebooks(gateway)
    text = _tool_list_notes_output(notebooks)
    assert "Test Notebook" in text
    assert "nb-1" in text
    assert "**" in text


@pytest.mark.asyncio
async def test_tool_list_note_sections_output_format():
    """Tool list_note_sections output format matches expected markdown."""
    gateway = MockOneNoteGateway()
    sections = await list_sections(gateway, notebook_id="nb-1")
    text = _tool_list_sections_output(sections)
    assert "Test Section" in text
    assert "sec-1" in text


@pytest.mark.asyncio
async def test_tool_read_note_content_output():
    """Tool read_note_content returns HTML or fallback."""
    gateway = MockOneNoteGateway()
    content = await get_note_content(gateway, page_id="page-1")
    assert content
    assert "Hello from the note" in content


# ---- App structure (routes mounted) ----


def test_combined_app_has_sse_and_streamable_routes(app):
    """Combined app mounts routes from both SSE and Streamable HTTP (multiple routes)."""
    routes = list(app.router.routes)
    paths = []
    for r in routes:
        if hasattr(r, "path") and r.path:
            paths.append(r.path)
    # We expect at least /sse and /mcp from FastMCP defaults
    path_str = " ".join(paths)
    assert "/sse" in path_str or "sse" in path_str
    assert "/mcp" in path_str or "mcp" in path_str


@pytest.mark.asyncio
async def test_mock_gateway_list_notebooks_empty_user_id():
    """Mock gateway accepts user_id=None."""
    gateway = MockOneNoteGateway()
    notebooks = await gateway.list_notebooks(user_id=None)
    assert len(notebooks) == 1
