"""Entrypoint: run OneNote MCP server with both SSE and Streamable HTTP (no config)."""

import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# MCP SDK reads host/port from FASTMCP_HOST / FASTMCP_PORT (set before importing server)
if "FASTMCP_PORT" not in os.environ:
    os.environ["FASTMCP_PORT"] = os.environ.get("PORT", "8000")
if "FASTMCP_HOST" not in os.environ:
    os.environ["FASTMCP_HOST"] = os.environ.get("HOST", "0.0.0.0")


def get_combined_app():
    """Build and return the combined Starlette app (SSE + Streamable HTTP). Used by main() and tests."""
    from starlette.applications import Starlette

    from onenote_mcp.server import mcp

    sse_app = mcp.sse_app(mount_path="/")
    streamable_app = mcp.streamable_http_app()
    combined_routes = list(sse_app.router.routes) + list(streamable_app.router.routes)
    return Starlette(
        debug=mcp.settings.debug,
        routes=combined_routes,
        lifespan=streamable_app.router.lifespan_context,
    )


def main() -> None:
    """Run the MCP server with both SSE and Streamable HTTP on the same port."""
    import anyio

    from onenote_mcp.server import mcp

    combined_app = get_combined_app()

    async def serve() -> None:
        import uvicorn
        config = uvicorn.Config(
            combined_app,
            host=mcp.settings.host,
            port=mcp.settings.port,
            log_level=mcp.settings.log_level.lower(),
        )
        server = uvicorn.Server(config)
        await server.serve()

    anyio.run(serve)


if __name__ == "__main__":
    main()
    sys.exit(0)
