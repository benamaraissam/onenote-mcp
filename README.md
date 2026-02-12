# OneNote MCP Server

MCP server (SSE & Streamable HTTP) that connects to **OneNote** via Microsoft Graph and exposes tools to **list your notes** and **read each note’s content**. Built with the official [Model Context Protocol (MCP) Python SDK](https://github.com/modelcontextprotocol/python-sdk) and a clean, layered architecture.

## Features

- **Transports**: **Streamable HTTP** (default) and **SSE** (Server-Sent Events)
- **Tools**:
  - `list_notes` — list all OneNote notebooks
  - `list_note_sections` — list sections in a notebook
  - `list_note_pages` — list pages (in a section or all)
  - `read_note_content` — get the HTML content of a page
- **Auth**: Microsoft Graph via Azure Identity (delegated or application)

## Architecture

```
src/onenote_mcp/
├── domain/           # Models and ports (interfaces)
│   ├── models.py     # Notebook, Section, Page
│   └── ports.py      # OneNoteGateway
├── application/      # Use cases
│   └── use_cases.py  # list_notebooks, list_sections, list_pages, get_note_content
├── infrastructure/   # Microsoft Graph
│   └── graph_client.py  # GraphOneNoteGateway
├── server.py        # MCP FastMCP app + tools
└── main.py          # Entrypoint (SSE / Streamable HTTP)
```

- **Domain**: entities and gateway interface; no framework or Graph details.
- **Application**: use cases that call the gateway.
- **Infrastructure**: Graph API implementation of the gateway.
- **Server**: MCP (FastMCP) tools that use the use cases and lifespan-injected gateway.

## Requirements

- Python ≥ 3.10
- Azure app registration with **Notes.Read** (delegated) or **Notes.Read.All** (application)

## Setup

### 1. Clone and install

```bash
cd onenote
python3 -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -e .
```

This installs the package in editable mode so `onenote_mcp` is on your path. Alternatively:

```bash
pip install -r requirements.txt
pip install -e .
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv sync
```

### 2. Azure app registration

1. In [Azure Portal](https://portal.azure.com) → **App registrations** → **New registration** (name e.g. "OneNote MCP").
2. **API permissions** → Add permission → **Microsoft Graph** → **Delegated**:
   - `Notes.Read` (or `Notes.ReadWrite`)
   - `User.Read`
3. **Authentication** → **Add a platform** → **Mobile and desktop applications** → add a redirect URI (e.g. **`http://localhost:8400`**; must match `AZURE_REDIRECT_URI` in `.env`) → Save. Then set **Allow public client flows** = **Yes**.
4. In `.env`: set `AZURE_CLIENT_ID`; optionally `AZURE_TENANT_ID` and `AZURE_REDIRECT_URI` (default `http://localhost:8400`).
5. For **application** (app-only) auth instead: add **Application** permission `Notes.Read.All`, create a client secret, and set `ONENOTE_USER_ID`.

### 3. Environment

```bash
cp .env.example .env
```

- **Delegated (browser login)**: set `AZURE_CLIENT_ID` (and optionally `AZURE_TENANT_ID`) to your app registration from step 2. First run will open the browser to sign in.
- **Application (app-only)**: set `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, and `ONENOTE_USER_ID`.

## Running the server

If you get `ModuleNotFoundError: No module named 'onenote_mcp'`, install the package first: `pip install -e .`

**Both SSE and Streamable HTTP** run on the same server (no config to choose):

```bash
python -m onenote_mcp.main
# or after pip install -e .
onenote-mcp
```

**Custom host/port**:

```bash
PORT=3000 python -m onenote_mcp.main
HOST=0.0.0.0 PORT=8000 python -m onenote_mcp.main
```

## Connecting a client

Both transports are available on the same server. Use whichever your client supports.

**Streamable HTTP** — single URL:

- `http://localhost:8000/mcp` (or your `HOST`/`PORT`)

```json
{
  "mcpServers": {
    "onenote": {
      "type": "streamable-http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

**SSE** — connect to the SSE endpoint; the server will tell the client where to POST messages:

- SSE: `GET http://localhost:8000/sse`
- Messages: `POST http://localhost:8000/messages/` (with `?session_id=...` from the first SSE event)

```json
{
  "mcpServers": {
    "onenote": {
      "type": "sse",
      "url": "http://localhost:8000/sse"
    }
  }
}
```

## Tools reference

| Tool | Description |
|------|-------------|
| `list_notes` | List all OneNote notebooks. Optional: `user_id` (for app-only). |
| `list_note_sections` | List sections in a notebook. Required: `notebook_id`. Optional: `user_id`. |
| `list_note_pages` | List pages; optional `section_id` to limit to one section. Optional: `user_id`. |
| `read_note_content` | Get HTML content of a page. Required: `page_id`. Optional: `user_id`. |

Use IDs from `list_notes` / `list_note_sections` / `list_note_pages` as inputs to the next tool.

## Testing

Install dev dependencies and run tests (mock OneNote gateway, no Azure credentials):

```bash
pip install -e ".[dev]"
# or
pip install -r requirements-dev.txt
pytest tests/ -v
```

Tests use a mock gateway and run offline. They cover:

- **Use cases**: `list_notebooks`, `list_sections`, `list_pages`, `get_note_content` with mock data
- **Tool output format**: markdown/HTML shape of tool responses
- **App structure**: combined app mounts `/sse` and `/mcp` routes

## License

MIT.
