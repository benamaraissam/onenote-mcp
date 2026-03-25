"""Entrypoint: run OneNote MCP server with Streamable HTTP transport."""

import os

try:
    from dotenv import load_dotenv

    # Later entries in .env override earlier ones (and override stale shell vars).
    load_dotenv(override=True)
except ImportError:
    pass

from onenote_mcp.server import mcp

app = mcp.http_app()


def main() -> None:
    mcp.run(
        transport="streamable-http",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
    )


if __name__ == "__main__":
    main()
