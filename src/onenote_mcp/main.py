"""Entrypoint: run OneNote MCP server with Streamable HTTP transport."""

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from onenote_mcp.server import mcp


def main() -> None:
    mcp.run(
        transport="streamable-http",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
    )


if __name__ == "__main__":
    main()
