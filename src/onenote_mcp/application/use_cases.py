"""OneNote use cases: delegate to gateway and return domain models."""

from onenote_mcp.domain.ports import OneNoteGateway


async def list_notebooks(gateway: OneNoteGateway, user_id: str | None = None):
    """List all OneNote notebooks for the user."""
    return await gateway.list_notebooks(user_id=user_id)


async def list_sections(
    gateway: OneNoteGateway,
    notebook_id: str,
    user_id: str | None = None,
):
    """List all sections in a notebook."""
    return await gateway.list_sections(notebook_id=notebook_id, user_id=user_id)


async def list_pages(
    gateway: OneNoteGateway,
    section_id: str | None = None,
    notebook_id: str | None = None,
    user_id: str | None = None,
):
    """List pages: in a section, or all pages for the user."""
    return await gateway.list_pages(
        section_id=section_id,
        notebook_id=notebook_id,
        user_id=user_id,
    )


async def get_note_content(
    gateway: OneNoteGateway,
    page_id: str,
    user_id: str | None = None,
) -> str:
    """Get the HTML content of a OneNote page."""
    return await gateway.get_page_content(page_id=page_id, user_id=user_id)
