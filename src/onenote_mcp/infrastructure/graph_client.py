"""Microsoft Graph implementation of OneNote gateway."""

import os
from typing import Any

from azure.identity import ClientSecretCredential, InteractiveBrowserCredential
from msgraph import GraphServiceClient

from onenote_mcp.domain.models import Notebook, Page, Section
from onenote_mcp.domain.ports import OneNoteGateway


def _to_dict(obj: Any) -> dict[str, Any]:
    """Convert SDK model to dict (additional_data or attributes)."""
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "additional_data") and obj.additional_data:
        return dict(obj.additional_data)
    out: dict[str, Any] = {}
    for k in dir(obj):
        if k.startswith("_") or k in ("get_query_parameter", "path_parameters", "request_adapter"):
            continue
        try:
            v = getattr(obj, k)
            if not callable(v) and v is not None:
                out[k] = v
        except Exception:
            pass
    return out


def _to_dict_list(value: Any) -> list[dict[str, Any]]:
    """Extract list of dicts from SDK response (response.value)."""
    if value is None:
        return []
    if isinstance(value, list):
        return [_to_dict(item) for item in value]
    if hasattr(value, "value") and value.value is not None:
        return [_to_dict(item) for item in value.value]
    return []


class GraphOneNoteGateway(OneNoteGateway):
    """OneNote gateway using Microsoft Graph API."""

    def __init__(
        self,
        *,
        tenant_id: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        user_id: str | None = None,
        redirect_uri: str | None = None,
    ) -> None:
        tenant_id = tenant_id or os.environ.get("AZURE_TENANT_ID")
        client_id = client_id or os.environ.get("AZURE_CLIENT_ID")
        client_secret = client_secret or os.environ.get("AZURE_CLIENT_SECRET")
        self._user_id = user_id or os.environ.get("ONENOTE_USER_ID")
        redirect_uri = redirect_uri or os.environ.get("AZURE_REDIRECT_URI", "http://localhost:8400")

        if tenant_id and client_id and client_secret:
            credential = ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret,
            )
            scopes = ["https://graph.microsoft.com/.default"]
        else:
            # Delegated auth: you must use an app registration with Notes.Read (delegated) and allow public client
            if not client_id:
                raise ValueError(
                    "For delegated (browser) login, set AZURE_CLIENT_ID (and optionally AZURE_TENANT_ID) to your app registration. "
                    "In Azure Portal: App registration → API permissions → Add delegated: Notes.Read, User.Read; "
                    "Authentication → Allow public client flows = Yes."
                )
            credential = InteractiveBrowserCredential(
                tenant_id=tenant_id or "organizations",
                client_id=client_id,
                redirect_uri=redirect_uri,
            )
            scopes = [
                "https://graph.microsoft.com/User.Read",
                "https://graph.microsoft.com/Notes.Read",
            ]

        self._client = GraphServiceClient(credentials=credential, scopes=scopes)

    def _onenote(self, user_id: str | None = None):
        """Onenote request builder: me (delegated) or users/{id} (app-only)."""
        uid = user_id or self._user_id
        if uid:
            return self._client.users.by_user_id(uid).onenote
        return self._client.me.onenote

    async def list_notebooks(self, user_id: str | None = None) -> list[Notebook]:
        onenote = self._onenote(user_id)
        response = await onenote.notebooks.get()
        raw = _to_dict_list(response)
        return [Notebook.from_graph(item) for item in raw]

    async def list_sections(
        self,
        notebook_id: str,
        user_id: str | None = None,
    ) -> list[Section]:
        onenote = self._onenote(user_id)
        response = await onenote.notebooks.by_notebook_id(notebook_id).sections.get()
        raw = _to_dict_list(response)
        return [Section.from_graph(item, notebook_id=notebook_id) for item in raw]

    async def list_pages(
        self,
        section_id: str | None = None,
        notebook_id: str | None = None,
        user_id: str | None = None,
    ) -> list[Page]:
        onenote = self._onenote(user_id)
        if section_id:
            response = await onenote.sections.by_onenote_section_id(section_id).pages.get()
            raw = _to_dict_list(response)
            return [Page.from_graph(item, section_id=section_id, notebook_id=notebook_id) for item in raw]
        response = await onenote.pages.get()
        raw = _to_dict_list(response)
        return [Page.from_graph(item) for item in raw]

    async def get_page_content(
        self,
        page_id: str,
        user_id: str | None = None,
    ) -> str:
        onenote = self._onenote(user_id)
        result = await onenote.pages.by_onenote_page_id(page_id).content.get()
        if result is None:
            return ""
        if isinstance(result, bytes):
            return result.decode("utf-8", errors="replace")
        return str(result)
