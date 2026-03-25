"""Entrypoint: run OneNote MCP server with Streamable HTTP transport."""

import os

try:
    from dotenv import load_dotenv

    load_dotenv(override=True)
except ImportError:
    pass

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from onenote_mcp.server import mcp


async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


app = Starlette(
    routes=[
        Route("/health", health),
        Mount("/", app=mcp.http_app()),
    ],
)


def main() -> None:
    mcp.run(
        transport="streamable-http",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
    )


if __name__ == "__main__":
    main()
