"""MCP server: SSE & Streamable HTTP with OneNote tools."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

from onenote_mcp.application.use_cases import (
    get_note_content,
    list_notebooks,
    list_pages,
    list_sections,
)
from onenote_mcp.infrastructure.graph_client import GraphOneNoteGateway


@dataclass
class AppContext:
    """Lifespan context: shared OneNote gateway."""

    gateway: GraphOneNoteGateway


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Create Graph gateway on startup, cleanup on shutdown."""
    gateway = GraphOneNoteGateway(
        tenant_id=os.environ.get("AZURE_TENANT_ID"),
        client_id=os.environ.get("AZURE_CLIENT_ID"),
        client_secret=os.environ.get("AZURE_CLIENT_SECRET"),
        user_id=os.environ.get("ONENOTE_USER_ID"),
        redirect_uri=os.environ.get("AZURE_REDIRECT_URI"),
    )
    try:
        yield AppContext(gateway=gateway)
    finally:
        pass


mcp = FastMCP(
    "OneNote",
    json_response=True,
    lifespan=app_lifespan,
)


def _get_gateway(ctx: Context[ServerSession, AppContext]) -> GraphOneNoteGateway:
    return ctx.request_context.lifespan_context.gateway


@mcp.tool()
async def list_notes(ctx: Context[ServerSession, AppContext], user_id: str | None = None) -> str:
    """List all OneNote notebooks for the user (or for the given user_id in app-only auth)."""
    gateway = _get_gateway(ctx)
    notebooks = await list_notebooks(gateway, user_id=user_id)
    if not notebooks:
        return "No notebooks found."
    lines = []
    for n in notebooks:
        lines.append(f"- **{n.display_name}** (id: `{n.id}`)")
    return "\n".join(lines)


@mcp.tool()
async def list_note_sections(
    ctx: Context[ServerSession, AppContext],
    notebook_id: str,
    user_id: str | None = None,
) -> str:
    """List all sections in a OneNote notebook. Use notebook_id from list_notes."""
    gateway = _get_gateway(ctx)
    sections = await list_sections(gateway, notebook_id=notebook_id, user_id=user_id)
    if not sections:
        return "No sections found in this notebook."
    lines = []
    for s in sections:
        lines.append(f"- **{s.display_name}** (id: `{s.id}`)")
    return "\n".join(lines)


@mcp.tool()
async def list_note_pages(
    ctx: Context[ServerSession, AppContext],
    section_id: str | None = None,
    user_id: str | None = None,
) -> str:
    """List OneNote pages. If section_id is given, list pages in that section; otherwise list all pages for the user."""
    gateway = _get_gateway(ctx)
    pages = await list_pages(
        gateway,
        section_id=section_id,
        user_id=user_id,
    )
    if not pages:
        return "No pages found."
    lines = []
    for p in pages:
        lines.append(f"- **{p.title or '(untitled)'}** (id: `{p.id}`)")
    return "\n".join(lines)


@mcp.tool()
async def read_note_content(
    ctx: Context[ServerSession, AppContext],
    page_id: str,
    user_id: str | None = None,
) -> str:
    """Get the HTML content of a OneNote page. Use page_id from list_note_pages."""
    gateway = _get_gateway(ctx)
    content = await get_note_content(gateway, page_id=page_id, user_id=user_id)
    return content or "(empty page)"
