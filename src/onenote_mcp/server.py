"""MCP server: Streamable HTTP with OneNote tools.

Supports three auth modes via AUTH_MODE env var:
  - oauth2        : AzureProvider + On-Behalf-Of flow (single app registration)
  - oauth2_proxy  : OAuthProxy with separate client/server apps + manual OBO
  - az_cli        : No MCP-level auth; Graph token obtained from Azure CLI
"""

from __future__ import annotations

import os

from fastmcp import FastMCP

from onenote_mcp.application.use_cases import (
    get_note_content,
    list_notebooks,
    list_pages,
    list_sections,
)
from onenote_mcp.infrastructure.graph_client import GraphOneNoteGateway

AUTH_MODE = os.environ.get("AUTH_MODE", "oauth2").lower()

GRAPH_SCOPES = [
    "https://graph.microsoft.com/User.Read",
    "https://graph.microsoft.com/Notes.Read",
    "https://graph.microsoft.com/Notes.Read.All",
    "https://graph.microsoft.com/Group.Read.All",
]


def _build_mcp() -> FastMCP:
    if AUTH_MODE == "oauth2":
        from fastmcp.server.auth.providers.azure import AzureProvider

        auth = AzureProvider(
            client_id=os.environ["AZURE_CLIENT_ID"],
            client_secret=os.environ["AZURE_CLIENT_SECRET"],
            tenant_id=os.environ["AZURE_TENANT_ID"],
            base_url=os.environ.get("MCP_BASE_URL", "http://localhost:8000"),
            required_scopes=["mcp-access"],
            additional_authorize_scopes=GRAPH_SCOPES + ["offline_access"],
        )
        return FastMCP("OneNote", auth=auth)

    if AUTH_MODE == "oauth2_proxy":
        from fastmcp.server.auth.providers.jwt import JWTVerifier

        from onenote_mcp.infrastructure.azure_oauth_proxy import AzureOAuthProxy

        tenant_id = os.environ["AZURE_TENANT_ID"]
        server_client_id = os.environ["AZURE_SERVER_CLIENT_ID"]
        scope_uri = f"api://{server_client_id}/mcp-access"
        # Azure v2 tokens may use aud = app id or App ID URI; scp often includes full scope URI.
        api_audiences = [
            server_client_id,
            f"api://{server_client_id}",
        ]

        # Entra often puts the short scope name in `scp` (e.g. mcp-access), not api://.../mcp-access.
        # Requiring the full URI makes JWTVerifier reject valid tokens (see jwt.py scope check).
        # Audience already binds the token to the server app (App A).
        extra_aud = (os.environ.get("AZURE_SERVER_AUDIENCE") or "").strip()
        if extra_aud:
            api_audiences = [*api_audiences, extra_aud]

        token_verifier = JWTVerifier(
            jwks_uri=f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys",
            issuer=f"https://login.microsoftonline.com/{tenant_id}/v2.0",
            audience=api_audiences,
            required_scopes=None,
        )

        # App B: Web registrations need a client secret at the token endpoint (AADSTS7000218).
        # Public client + "Allow public client flows" can use no secret (token_endpoint_auth_method=none).
        client_b_secret = (os.environ.get("AZURE_CLIENT_SECRET") or "").strip()
        if client_b_secret:
            proxy_secret = client_b_secret
            proxy_token_auth: str | None = "client_secret_post"
        else:
            proxy_secret = "unused"
            proxy_token_auth = "none"

        auth = AzureOAuthProxy(
            upstream_authorization_endpoint=(
                f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize"
            ),
            upstream_token_endpoint=(
                f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
            ),
            upstream_client_id=os.environ["AZURE_CLIENT_ID"],
            upstream_client_secret=proxy_secret,
            token_endpoint_auth_method=proxy_token_auth,
            token_verifier=token_verifier,
            base_url=os.environ.get("MCP_BASE_URL", "http://localhost:8000"),
            valid_scopes=[scope_uri],
            require_authorization_consent=False,
        )
        return FastMCP("OneNote", auth=auth)

    return FastMCP("OneNote")


mcp = _build_mcp()


# ---------------------------------------------------------------------------
# Graph token resolution per mode
# ---------------------------------------------------------------------------

async def _get_graph_token_oauth2(obo_token: str) -> str:
    return obo_token


async def _get_graph_token_proxy(upstream_token: str) -> str:
    from onenote_mcp.infrastructure.obo_token import exchange_obo_token

    return await exchange_obo_token(
        assertion=upstream_token,
        server_client_id=os.environ["AZURE_SERVER_CLIENT_ID"],
        server_client_secret=os.environ["AZURE_SERVER_CLIENT_SECRET"],
        tenant_id=os.environ["AZURE_TENANT_ID"],
    )


async def _get_graph_token_azcli() -> str:
    from onenote_mcp.infrastructure.az_cli_token import get_graph_token

    return await get_graph_token()


# ---------------------------------------------------------------------------
# Register tools based on auth mode
# ---------------------------------------------------------------------------

if AUTH_MODE == "oauth2":
    from fastmcp.server.auth.providers.azure import EntraOBOToken

    @mcp.tool
    async def list_notes(
        graph_token: str = EntraOBOToken(GRAPH_SCOPES),
    ) -> str:
        """List all OneNote notebooks for the authenticated user."""
        token = await _get_graph_token_oauth2(graph_token)
        gateway = GraphOneNoteGateway(graph_token=token)
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
        token = await _get_graph_token_oauth2(graph_token)
        gateway = GraphOneNoteGateway(graph_token=token)
        sections = await list_sections(gateway, notebook_id=notebook_id)
        if not sections:
            return "No sections found in this notebook."
        lines = []
        for s in sections:
            lines.append(f"- **{s.display_name}** (id: `{s.id}`)")
        return "\n".join(lines)

    @mcp.tool
    async def list_note_pages(
        section_id: str | None = None,
        graph_token: str = EntraOBOToken(GRAPH_SCOPES),
    ) -> str:
        """List OneNote pages. If section_id is given, list pages in that section; otherwise list all pages for the user."""
        token = await _get_graph_token_oauth2(graph_token)
        gateway = GraphOneNoteGateway(graph_token=token)
        pages = await list_pages(gateway, section_id=section_id)
        if not pages:
            return "No pages found."
        lines = []
        for p in pages:
            lines.append(f"- **{p.title or '(untitled)'}** (id: `{p.id}`)")
        return "\n".join(lines)

    @mcp.tool
    async def read_note_content(
        page_id: str,
        graph_token: str = EntraOBOToken(GRAPH_SCOPES),
    ) -> str:
        """Get the HTML content of a OneNote page. Use page_id from list_note_pages."""
        token = await _get_graph_token_oauth2(graph_token)
        gateway = GraphOneNoteGateway(graph_token=token)
        content = await get_note_content(gateway, page_id=page_id)
        return content or "(empty page)"

elif AUTH_MODE == "oauth2_proxy":
    from fastmcp.dependencies import CurrentAccessToken
    from fastmcp.server.auth import AccessToken

    @mcp.tool
    async def list_notes(  # type: ignore[no-redef]
        access_token: AccessToken = CurrentAccessToken(),
    ) -> str:
        """List all OneNote notebooks for the authenticated user."""
        token = await _get_graph_token_proxy(access_token.token)
        gateway = GraphOneNoteGateway(graph_token=token)
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
    async def list_note_sections(  # type: ignore[no-redef]
        notebook_id: str,
        access_token: AccessToken = CurrentAccessToken(),
    ) -> str:
        """List all sections in a OneNote notebook. Use notebook_id from list_notes."""
        token = await _get_graph_token_proxy(access_token.token)
        gateway = GraphOneNoteGateway(graph_token=token)
        sections = await list_sections(gateway, notebook_id=notebook_id)
        if not sections:
            return "No sections found in this notebook."
        lines = []
        for s in sections:
            lines.append(f"- **{s.display_name}** (id: `{s.id}`)")
        return "\n".join(lines)

    @mcp.tool
    async def list_note_pages(  # type: ignore[no-redef]
        section_id: str | None = None,
        access_token: AccessToken = CurrentAccessToken(),
    ) -> str:
        """List OneNote pages. If section_id is given, list pages in that section; otherwise list all pages for the user."""
        token = await _get_graph_token_proxy(access_token.token)
        gateway = GraphOneNoteGateway(graph_token=token)
        pages = await list_pages(gateway, section_id=section_id)
        if not pages:
            return "No pages found."
        lines = []
        for p in pages:
            lines.append(f"- **{p.title or '(untitled)'}** (id: `{p.id}`)")
        return "\n".join(lines)

    @mcp.tool
    async def read_note_content(  # type: ignore[no-redef]
        page_id: str,
        access_token: AccessToken = CurrentAccessToken(),
    ) -> str:
        """Get the HTML content of a OneNote page. Use page_id from list_note_pages."""
        token = await _get_graph_token_proxy(access_token.token)
        gateway = GraphOneNoteGateway(graph_token=token)
        content = await get_note_content(gateway, page_id=page_id)
        return content or "(empty page)"

else:

    @mcp.tool
    async def list_notes() -> str:  # type: ignore[no-redef]
        """List all OneNote notebooks for the authenticated user."""
        token = await _get_graph_token_azcli()
        gateway = GraphOneNoteGateway(graph_token=token)
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
    async def list_note_sections(notebook_id: str) -> str:  # type: ignore[no-redef]
        """List all sections in a OneNote notebook. Use notebook_id from list_notes."""
        token = await _get_graph_token_azcli()
        gateway = GraphOneNoteGateway(graph_token=token)
        sections = await list_sections(gateway, notebook_id=notebook_id)
        if not sections:
            return "No sections found in this notebook."
        lines = []
        for s in sections:
            lines.append(f"- **{s.display_name}** (id: `{s.id}`)")
        return "\n".join(lines)

    @mcp.tool
    async def list_note_pages(section_id: str | None = None) -> str:  # type: ignore[no-redef]
        """List OneNote pages. If section_id is given, list pages in that section; otherwise list all pages for the user."""
        token = await _get_graph_token_azcli()
        gateway = GraphOneNoteGateway(graph_token=token)
        pages = await list_pages(gateway, section_id=section_id)
        if not pages:
            return "No pages found."
        lines = []
        for p in pages:
            lines.append(f"- **{p.title or '(untitled)'}** (id: `{p.id}`)")
        return "\n".join(lines)

    @mcp.tool
    async def read_note_content(page_id: str) -> str:  # type: ignore[no-redef]
        """Get the HTML content of a OneNote page. Use page_id from list_note_pages."""
        token = await _get_graph_token_azcli()
        gateway = GraphOneNoteGateway(graph_token=token)
        content = await get_note_content(gateway, page_id=page_id)
        return content or "(empty page)"
