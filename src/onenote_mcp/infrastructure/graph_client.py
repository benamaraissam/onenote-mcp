"""Microsoft Graph implementation of OneNote gateway using an OBO access token."""

import logging
import re
from typing import Any

import httpx

from onenote_mcp.domain.models import Notebook, Page, Section
from onenote_mcp.domain.ports import OneNoteGateway

_log = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

_SECTION_KEYS = frozenset(
    {"id", "displayName", "self", "pagesUrl",
     "createdDateTime", "lastModifiedDateTime"}
)
_PAGE_KEYS = frozenset(
    {"id", "title", "contentUrl", "self",
     "createdDateTime", "lastModifiedDateTime"}
)


def _normalize_id(raw_id: Any) -> str:
    """Extract a clean API id from OData refs or URLs."""
    if raw_id is None:
        return ""
    s = str(raw_id).strip()
    if not s:
        return ""
    if re.match(r"^[\w\-!]+$", s) and "metadata#" not in s and "(" not in s and "/" not in s:
        return s
    if "metadata#" in s or s.startswith("http") or "/" in s:
        parts = re.split(r"[/#)]", s)
        best = ""
        for part in reversed(parts):
            part = (part or "").strip()
            if not part or part.startswith("users") or "(" in part:
                continue
            if not re.match(r"^[\w\-!]+$", part) or len(part) < 6:
                continue
            if re.match(r"^\d[\w\-]+$", part) or re.match(r"^[0-9a-f\-]{20,}$", part, re.I):
                return part
            best = part
        return best or s
    return s


def _clean_section_item(raw: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in raw.items():
        if k not in _SECTION_KEYS:
            continue
        if k == "id":
            out[k] = _normalize_id(v) or (str(v) if v is not None else "")
            continue
        if k == "displayName" and v is not None:
            s = str(v).strip()
            if s and not s.startswith("metadata#") and not s.startswith("http"):
                out["display_name"] = s
            continue
        out[k] = v
    if "id" not in out and "id" in raw:
        out["id"] = _normalize_id(raw["id"]) or str(raw["id"])
    return out


def _clean_page_item(raw: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in raw.items():
        if k not in _PAGE_KEYS:
            continue
        if k == "id":
            out[k] = _normalize_id(v) or (str(v) if v is not None else "")
            continue
        if k == "title" and v is not None:
            s = str(v).strip()
            if s and not s.startswith("metadata#") and not s.startswith("http"):
                out[k] = s
            continue
        out[k] = v
    if "id" not in out and "id" in raw:
        out["id"] = _normalize_id(raw["id"]) or str(raw["id"])
    return out


class GraphOneNoteGateway(OneNoteGateway):
    """OneNote gateway using Microsoft Graph API with a pre-obtained OBO access token."""

    def __init__(self, *, graph_token: str) -> None:
        self._token = graph_token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    async def _get_json(self, url: str) -> Any:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self._headers(), timeout=30)
            if resp.status_code >= 400:
                _log.error("Graph API %s → %s: %s", url, resp.status_code, resp.text)
            resp.raise_for_status()
            return resp.json()

    async def _get_bytes(self, url: str) -> bytes:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self._headers(), timeout=30)
            if resp.status_code >= 400:
                _log.error("Graph API %s → %s: %s", url, resp.status_code, resp.text)
            resp.raise_for_status()
            return resp.content

    async def list_notebooks(self, user_id: str | None = None) -> list[Notebook]:
        data = await self._get_json(f"{GRAPH_BASE}/me/onenote/notebooks")
        raw = data.get("value", [])
        notebooks = [Notebook.from_graph(item) for item in raw]
        seen_ids = {n.id for n in notebooks}

        for gid in await self._get_group_ids():
            try:
                gdata = await self._get_json(
                    f"{GRAPH_BASE}/groups/{gid}/onenote/notebooks"
                )
                for item in gdata.get("value", []):
                    nb = Notebook.from_graph(item)
                    if nb.id not in seen_ids:
                        notebooks.append(nb)
                        seen_ids.add(nb.id)
            except httpx.HTTPStatusError:
                continue

        return notebooks

    async def _get_group_ids(self) -> list[str]:
        """Return IDs of unified (Microsoft 365) groups the user belongs to.

        Only unified groups can have OneNote notebooks. Security groups,
        distribution lists, etc. are skipped. Returns an empty list when
        the caller lacks Group.Read.All permission.
        """
        try:
            data = await self._get_json(
                f"{GRAPH_BASE}/me/memberOf/microsoft.graph.group"
                "?$filter=groupTypes/any(t:t eq 'Unified')"
                "&$select=id"
            )
            return [g["id"] for g in data.get("value", []) if g.get("id")]
        except httpx.HTTPStatusError:
            return []

    async def list_sections(
        self,
        notebook_id: str,
        user_id: str | None = None,
    ) -> list[Section]:
        try:
            data = await self._get_json(
                f"{GRAPH_BASE}/me/onenote/notebooks/{notebook_id}/sections"
            )
            raw = data.get("value", [])
            if raw:
                return [
                    Section.from_graph(_clean_section_item(item), notebook_id=notebook_id)
                    for item in raw
                ]
        except httpx.HTTPStatusError:
            pass

        for gid in await self._get_group_ids():
            try:
                gdata = await self._get_json(
                    f"{GRAPH_BASE}/groups/{gid}/onenote/notebooks/{notebook_id}/sections"
                )
                graw = gdata.get("value", [])
                if graw:
                    return [
                        Section.from_graph(_clean_section_item(item), notebook_id=notebook_id)
                        for item in graw
                    ]
            except httpx.HTTPStatusError:
                continue
        return []

    async def list_pages(
        self,
        section_id: str | None = None,
        notebook_id: str | None = None,
        user_id: str | None = None,
    ) -> list[Page]:
        if section_id:
            try:
                data = await self._get_json(
                    f"{GRAPH_BASE}/me/onenote/sections/{section_id}/pages"
                )
                raw = data.get("value", [])
                if raw:
                    return [
                        Page.from_graph(
                            _clean_page_item(item),
                            section_id=section_id,
                            notebook_id=notebook_id,
                        )
                        for item in raw
                    ]
            except httpx.HTTPStatusError:
                pass

            for gid in await self._get_group_ids():
                try:
                    gdata = await self._get_json(
                        f"{GRAPH_BASE}/groups/{gid}/onenote/sections/{section_id}/pages"
                    )
                    graw = gdata.get("value", [])
                    if graw:
                        return [
                            Page.from_graph(
                                _clean_page_item(item),
                                section_id=section_id,
                                notebook_id=notebook_id,
                            )
                            for item in graw
                        ]
                except httpx.HTTPStatusError:
                    continue
            return []

        data = await self._get_json(f"{GRAPH_BASE}/me/onenote/pages")
        raw = data.get("value", [])
        return [Page.from_graph(_clean_page_item(item)) for item in raw]

    async def get_page_content(
        self,
        page_id: str,
        user_id: str | None = None,
    ) -> str:
        try:
            content = await self._get_bytes(
                f"{GRAPH_BASE}/me/onenote/pages/{page_id}/content"
            )
            return content.decode("utf-8", errors="replace")
        except httpx.HTTPStatusError:
            pass

        for gid in await self._get_group_ids():
            try:
                content = await self._get_bytes(
                    f"{GRAPH_BASE}/groups/{gid}/onenote/pages/{page_id}/content"
                )
                return content.decode("utf-8", errors="replace")
            except httpx.HTTPStatusError:
                continue
        return ""
