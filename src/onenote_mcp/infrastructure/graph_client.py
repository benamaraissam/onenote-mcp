"""Microsoft Graph implementation of OneNote gateway."""

import os
import re
from typing import Any

from azure.identity import ClientSecretCredential, InteractiveBrowserCredential
from msgraph import GraphServiceClient

from onenote_mcp.domain.models import Notebook, Page, Section
from onenote_mcp.domain.ports import OneNoteGateway

# Keys we actually use for Section/Page from Graph; avoid OData refs (parent_notebook, etc.)
_SECTION_KEYS = frozenset(
    {"id", "display_name", "displayName", "self", "self_url", "pages_url", "pagesUrl",
     "created_date_time", "createdDateTime", "last_modified_date_time", "lastModifiedDateTime"}
)
_PAGE_KEYS = frozenset(
    {"id", "title", "content_url", "contentUrl", "self", "self_url",
     "created_date_time", "createdDateTime", "last_modified_date_time", "lastModifiedDateTime"}
)


def _normalize_id(raw_id: Any) -> str:
    """Extract a clean API id from OData refs like metadata#users('...')/parentNotebook/... or URLs."""
    if raw_id is None:
        return ""
    s = str(raw_id).strip()
    if not s:
        return ""
    # Already a short id (e.g. 1-abc-123 or guid-like, no metadata/URL)
    if re.match(r"^[\w\-!]+$", s) and "metadata#" not in s and "(" not in s and "/" not in s:
        return s
    # OData / URL: prefer segment that looks like OneNote id (digit + hyphen or GUID), else last segment
    if "metadata#" in s or s.startswith("http") or "/" in s:
        parts = re.split(r"[/#)]", s)
        best = ""
        for part in reversed(parts):
            part = (part or "").strip()
            if not part or part.startswith("users") or "(" in part:
                continue
            if not re.match(r"^[\w\-!]+$", part) or len(part) < 6:
                continue
            # Prefer OneNote-style id (e.g. 1-6fb566fe-454f-4de6-87f2-41d22a0e30dd)
            if re.match(r"^\d[\w\-]+$", part) or re.match(r"^[0-9a-f\-]{20,}$", part, re.I):
                return part
            best = part
        return best or s
    return s


def _to_dict(obj: Any) -> dict[str, Any]:
    """Convert SDK model to dict by reading its real attributes (not OData additional_data)."""
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    # Read actual attributes from the SDK model, skip OData noise in additional_data
    _SKIP = frozenset({
        "additional_data", "backing_store", "odata_type",
        "get_query_parameter", "path_parameters", "request_adapter",
        "get_field_deserializers", "serialize", "create_from_discriminator_value",
    })
    out: dict[str, Any] = {}
    for k in dir(obj):
        if k.startswith("_") or k in _SKIP:
            continue
        try:
            v = getattr(obj, k)
            if callable(v) or v is None:
                continue
            # Skip nested SDK objects (parent_notebook, parent_section, links, etc.)
            if hasattr(v, "additional_data") or hasattr(v, "backing_store"):
                continue
            # Skip lists of SDK objects
            if isinstance(v, list) and v and hasattr(v[0], "additional_data"):
                continue
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


def _clean_section_item(raw: dict[str, Any]) -> dict[str, Any]:
    """Keep only Section fields and normalize id/display_name so we don't surface OData metadata."""
    out: dict[str, Any] = {}
    for k, v in raw.items():
        if k not in _SECTION_KEYS:
            continue
        if k == "id":
            out[k] = _normalize_id(v) or (str(v) if v is not None else "")
            continue
        if k in ("display_name", "displayName") and v is not None:
            s = str(v).strip() if not isinstance(v, str) else v.strip()
            # Skip OData refs / URLs that sometimes end up in name fields
            if s and not s.startswith("metadata#") and not s.startswith("http"):
                out[k] = s
            continue
        out[k] = v
    if "id" not in out and "id" in raw:
        out["id"] = _normalize_id(raw["id"]) or str(raw["id"])
    return out


def _clean_page_item(raw: dict[str, Any]) -> dict[str, Any]:
    """Keep only Page fields and normalize id/title so we don't surface OData metadata."""
    out: dict[str, Any] = {}
    for k, v in raw.items():
        if k not in _PAGE_KEYS:
            continue
        if k == "id":
            out[k] = _normalize_id(v) or (str(v) if v is not None else "")
            continue
        if k == "title" and v is not None:
            s = str(v).strip() if not isinstance(v, str) else v.strip()
            if s and not s.startswith("metadata#") and not s.startswith("http"):
                out[k] = s
            continue
        out[k] = v
    if "id" not in out and "id" in raw:
        out["id"] = _normalize_id(raw["id"]) or str(raw["id"])
    return out


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
        return [Section.from_graph(_clean_section_item(item), notebook_id=notebook_id) for item in raw]

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
            return [Page.from_graph(_clean_page_item(item), section_id=section_id, notebook_id=notebook_id) for item in raw]
        response = await onenote.pages.get()
        raw = _to_dict_list(response)
        return [Page.from_graph(_clean_page_item(item)) for item in raw]

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
