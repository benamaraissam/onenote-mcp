"""MCP server: Streamable HTTP with OneNote tools (AzureProvider + OBO)."""

from __future__ import annotations

import logging
import os

from fastmcp import FastMCP
from fastmcp.server.auth.providers.azure import AzureProvider, EntraOBOToken

logging.getLogger("fastmcp").setLevel(logging.DEBUG)

from onenote_mcp.application.use_cases import (
    get_note_content,
    list_notebooks,
    list_pages,
    list_sections,
)
from onenote_mcp.infrastructure.graph_client import GraphOneNoteGateway

GRAPH_SCOPES = [
    "https://graph.microsoft.com/User.Read",
    "https://graph.microsoft.com/Notes.Read",
    "https://graph.microsoft.com/Notes.Read.All",
    "https://graph.microsoft.com/Group.Read.All",
]

tenant_id = os.environ["AZURE_TENANT_ID"]

auth = AzureProvider(
    client_id=os.environ["AZURE_CLIENT_ID"],
    client_secret=os.environ["AZURE_CLIENT_SECRET"],
    tenant_id=tenant_id,
    base_url=os.environ.get("MCP_BASE_URL", "http://localhost:8000"),
    required_scopes=["mcp-access"],
    additional_authorize_scopes=GRAPH_SCOPES + ["offline_access"],
)

# AzureProvider hardcodes the v2.0 issuer, but enterprise app registrations
# with accessTokenVersion=null (default) emit v1 tokens whose issuer is
# https://sts.windows.net/{tenant}//.  Accept both so it works regardless
# of the manifest setting.
auth._token_validator.issuer = [
    f"https://login.microsoftonline.com/{tenant_id}/v2.0",
    f"https://sts.windows.net/{tenant_id}/",
]

mcp = FastMCP("OneNote", auth=auth)


@mcp.tool
async def list_notes(
    graph_token: str = EntraOBOToken(GRAPH_SCOPES),
) -> str:
    """List all OneNote notebooks for the authenticated user."""
    gateway = GraphOneNoteGateway(graph_token=graph_token)
    notebooks = await list_notebooks(gateway)
    if not notebooks:
        return "No notebooks found."
    lines = []
    for n in notebooks:
        role_tag = ""
        if n.user_role:
            role_tag = f" [{n.user_role}]"
        elif n.is_shared:
            role_tag = " [shared]"
        lines.append(f"- **{n.display_name}**{role_tag} (id: `{n.id}`)")
    return "\n".join(lines)


@mcp.tool
async def list_note_sections(
    notebook_id: str,
    graph_token: str = EntraOBOToken(GRAPH_SCOPES),
) -> str:
    """List all sections in a OneNote notebook. Use notebook_id from list_notes."""
    gateway = GraphOneNoteGateway(graph_token=graph_token)
    sections = await list_sections(gateway, notebook_id=notebook_id)
    if not sections:
        return "No sections found in this notebook."
    lines = [f"- **{s.display_name}** (id: `{s.id}`)" for s in sections]
    return "\n".join(lines)


@mcp.tool
async def list_note_pages(
    section_id: str | None = None,
    graph_token: str = EntraOBOToken(GRAPH_SCOPES),
) -> str:
    """List OneNote pages. If section_id is given, list pages in that section; otherwise list all pages for the user."""
    gateway = GraphOneNoteGateway(graph_token=graph_token)
    pages = await list_pages(gateway, section_id=section_id)
    if not pages:
        return "No pages found."
    lines = [f"- **{p.title or '(untitled)'}** (id: `{p.id}`)" for p in pages]
    return "\n".join(lines)


@mcp.tool
async def read_note_content(
    page_id: str,
    graph_token: str = EntraOBOToken(GRAPH_SCOPES),
) -> str:
    """Get the HTML content of a OneNote page. Use page_id from list_note_pages."""
    gateway = GraphOneNoteGateway(graph_token=graph_token)
    content = await get_note_content(gateway, page_id=page_id)
    return content or "(empty page)"
