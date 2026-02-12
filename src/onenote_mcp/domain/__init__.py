"""Domain layer: models and ports for OneNote."""

from onenote_mcp.domain.models import Notebook, Page, Section
from onenote_mcp.domain.ports import OneNoteGateway

__all__ = ["Notebook", "Section", "Page", "OneNoteGateway"]
