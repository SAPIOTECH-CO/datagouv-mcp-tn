# datagouv-mcp-tn

A Model Context Protocol (MCP) server for [data.gouv.tn](https://data.gouv.tn) — the Tunisian open data portal. Built with [FastMCP](https://gofastmcp.com).

## Prerequisites

- **Python 3.13+** (see `.python-version`)
- **[uv](https://docs.astral.sh/uv/)** — Python package & project manager

### Install uv (if not already installed)

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## Project setup

Clone the repository and install all dependencies into an isolated virtual environment:

```bash
git clone https://github.com/<you>/datagouv-mcp-tn.git
cd datagouv-mcp-tn

uv sync          # creates .venv and installs dependencies from uv.lock
```

## Activating the virtual environment

After `uv sync`, activate the environment so `python` and installed tools are available in your shell.

**Linux / macOS**

```bash
source .venv/bin/activate        # bash / zsh
.venv/bin/activate.fish          # fish
```

**Windows (PowerShell)**

```powershell
.venv\Scripts\Activate.ps1
```

**Windows (cmd)**

```cmd
.venv\Scripts\activate.bat
```

Verify you're inside the venv:

```bash
which python     # should point to .venv/bin/python
python --version # 3.13.x
```

To leave the environment:

```bash
deactivate
```

> **Tip:** You never *have* to activate the venv — `uv run` executes any command inside the project environment automatically:
>
> ```bash
> uv run python main.py
> ```

## Using the source code

Architecture follows [datagouv/datagouv-mcp](https://github.com/datagouv/datagouv-mcp) (the official data.gouv.fr MCP server): one file per tool in `tools/`, API clients and shared utilities in `helpers/`, aggregated via a single `register_tools()` call.

```
datagouv-mcp-tn/
├── src/datagouv_mcp_tn/
│   ├── server.py              # FastMCP instance + /health route + register_tools()
│   ├── tools/                 # one file per tool, register_<name>_tool(mcp)
│   │   ├── __init__.py        #   register_tools(mcp) aggregation
│   │   ├── search_datasets.py
│   │   ├── suggest_datasets.py
│   │   ├── get_dataset_info.py
│   │   ├── list_dataset_resources.py
│   │   ├── get_resource_info.py
│   │   ├── search_organizations.py
│   │   ├── get_organization_info.py
│   │   ├── search_dataservices.py
│   │   ├── get_dataservice_info.py
│   │   ├── get_dataservice_openapi_spec.py
│   │   ├── download_and_parse_resource.py
│   │   ├── query_resource_data.py
│   │   └── get_metrics.py
│   ├── models/                 # Pydantic models for uData payloads
│   │   ├── __init__.py         #   re-exports
│   │   ├── common.py           #   Pagination, Sort, FieldFilter, PaginationInfo
│   │   ├── dataset.py          #   Dataset, OrganizationRef, LicenseRef
│   │   ├── resource.py         #   Resource, Checksum
│   │   ├── dataservice.py      #   Dataservice, Endpoint
│   │   └── metrics.py          #   Metrics (+ per-object subtypes)
│   └── helpers/
│       ├── api_client.py       # async uData API client (httpx)
│       ├── config.py           # Settings (pydantic-settings, reads .env)
│       ├── file_parser.py      # in-memory CSV/XLS/XLSX/ODS/JSON/GeoJSON parsing (pandas)
│       ├── document_inspector.py # PDF/DOCX/PPTX/HTML(Scrapy)/XML/images/ZIP/KMZ summaries
│       ├── i18n.py             # AR/FR/EN message catalog for tool output
│       ├── logging.py          # logger + log_tool decorator
│       ├── logging_config.py   # structured JSON logging (uvicorn-aware)
│       ├── query_cleaner.py    # stop-word removal for search queries (FR/AR)
│       └── mcp_tool_defaults.py  # READ_ONLY_EXTERNAL_API_TOOL annotations
├── tests/
│   └── test_tools.py          # pytest suite (in-memory MCP client)
├── main.py                    # entry point (transport set by FASTMCP_TRANSPORT)
├── pyproject.toml             # project metadata + dependencies
├── uv.lock                    # locked dependency versions (do not edit by hand)
├── .env.example               # copy to .env and fill in
└── .venv/                     # virtual environment (generated, git-ignored)
```

Run the project:

```bash
uv run python main.py                          # stdio transport (default)
FASTMCP_TRANSPORT=http uv run python main.py   # streamable HTTP on :8000
FASTMCP_TRANSPORT=sse uv run python main.py    # legacy SSE on :8000
```

### Transports

| Transport | Env value | Endpoint | Use case |
| --- | --- | --- | --- |
| **stdio** | `stdio` (default) | subprocess pipes | Local MCP clients (opencode, Claude Desktop...) launch and manage the server process |
| **HTTP** | `http` | `http://HOST:PORT/mcp` (+ `/health`) | Production deployments, remote clients. Recommended. |
| **SSE** | `sse` | `http://HOST:PORT/sse` | Backward compatibility only — older clients that don't support streamable HTTP |

Host/port for network transports are set with `FASTMCP_HOST` and `FASTMCP_PORT`.

Connecting a client:

```jsonc
// opencode / Claude Desktop style MCP config
{
  "mcpServers": {
    "datagouv-tn": {
      // local (stdio): the client launches the server itself
      "type": "local",
      "command": ["uv", "--directory", "/path/to/datagouv-mcp-tn", "run", "python", "main.py"]
    },
    "datagouv-tn-remote": {
      // remote (streamable HTTP): start the server first with FASTMCP_TRANSPORT=http
      "type": "remote",
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

Add a new dependency:

```bash
uv add <package>       # updates pyproject.toml + uv.lock automatically
uv remove <package>
```

Upgrade dependencies:

```bash
uv lock --upgrade && uv sync
```

## Tools

All tools are read-only (`readOnlyHint=True`) and query the uData API of data.gouv.tn:

| Tool | Description |
| --- | --- |
| `search_datasets` | Free-text search over datasets |
| `suggest_datasets` | Autocomplete dataset titles |
| `get_dataset_info` | Full metadata for one dataset |
| `list_dataset_resources` | Files inside a dataset (ID, format, size, URL) |
| `get_resource_info` | Detailed metadata for one resource |
| `search_organizations` | Search publishing organizations |
| `get_organization_info` | Full metadata for one organization |
| `search_dataservices` | Search published APIs (dataservices) |
| `get_dataservice_info` | Full metadata for one dataservice |
| `get_dataservice_openapi_spec` | Fetch & summarize a dataservice's OpenAPI spec (JSON) |
| `download_and_parse_resource` | Download + analyze any resource in memory: tabular preview, or PDF/DOCX/PPTX/HTML/XML/image/ZIP inspection |
| `query_resource_data` | Filter / sort / select rows of a tabular resource without leaving the chat |
| `get_metrics` | Usage metrics (views, followers, reuses...) for datasets/organizations/dataservices/reuses |

Rich rendering (FastMCP Prefab apps): `search_datasets`, `list_dataset_resources`
and `get_metrics` additionally return an interactive **structured view** — a
sortable/searchable `DataTable` for results and files, metric cards + bar chart
for metrics. The text output is unchanged; clients without UI support simply
ignore the extra channel (`helpers/prefab_views.py`).

Typical flows:

- Metadata: `search_datasets` → `get_dataset_info` → `list_dataset_resources` → `get_resource_info`
- Data analysis: `list_dataset_resources` → `download_and_parse_resource` → `query_resource_data`

Tabular formats parsed into DataFrames: **CSV, XLS, XLSX, ODS, JSON, GeoJSON** —
the formats actually found on data.gouv.tn (~80% of resources).

Everything else is inspected instead of rejected (`document_inspector`):

- **PDF** — page count, metadata, text preview
- **DOCX / PPTX** (and legacy OLE2 detection) — paragraph/slide summaries
- **HTML** — parsed with Scrapy selectors: title, meta description, link/table/
  image/form counts, headings, visible-text preview (scripts/styles dropped)
- **XML / KML** — root element, placemark counts for geographic data
- **SVG / PNG / JPEG / GIF** — dimensions, mode, frame count
- **ZIP / KMZ** — entry listing with sizes; tabular members flagged; KMZ
  placemark count extracted from the inner KML
- **TXT & unknown payloads** — line/char counts, delimiter sniffing,
  magic-byte-based format guesses

Format hints from the portal are unreliable (`word`, `test`, `.JPG`, ...), so
detection combines normalized extensions with magic-byte sniffing.

## Adding a new tool

1. Create `src/datagouv_mcp_tn/tools/<tool_name>.py` following the existing pattern:

   ```python
   from fastmcp import FastMCP

   from datagouv_mcp_tn.helpers import api_client
   from datagouv_mcp_tn.helpers.logging import log_tool
   from datagouv_mcp_tn.helpers.mcp_tool_defaults import READ_ONLY_EXTERNAL_API_TOOL


   def register_my_tool(mcp: FastMCP) -> None:
       @mcp.tool(title="My tool", annotations=READ_ONLY_EXTERNAL_API_TOOL)
       @log_tool
       async def my_tool(param: str) -> str:
           """What the tool does and when the model should use it."""
           try:
               data = await api_client.get_something(param)
           except Exception as e:  # noqa: BLE001
               return f"Error: {e}"
           return f"Result for {param}: {data}"
   ```

2. Register it in `src/datagouv_mcp_tn/tools/__init__.py` inside `register_tools()`.
3. If it needs a new API call, add a function in `helpers/api_client.py` instead of calling `_get_json` from the tool directly.
4. Add a test in `tests/test_tools.py` (mock at the `api_client` boundary, use the in-memory client).

## Testing

```bash
uv run pytest            # all tests
uv run pytest -v         # verbose
```

Tests run against an in-memory MCP client with the API mocked — no network required.

Inspect the server interactively during development:

```bash
fastmcp dev main.py
```

## Configuration

Copy `.env.example` to `.env` and adjust. All variables are optional:

| Variable | Default | Description |
| --- | --- | --- |
| `DATA_GOUV_TN_API_URL` | `https://data.gouv.tn/api/1` | Base URL of the uData API |
| `DATA_GOUV_TN_API_KEY` | *(empty)* | API key, sent as `X-API-KEY` header if set |
| `FASTMCP_TRANSPORT` | `stdio` | `stdio`, `http`, or `sse` |
| `FASTMCP_HOST` | `127.0.0.1` | Bind host for `http` / `sse` transports |
| `FASTMCP_PORT` | `8000` | Bind port for `http` / `sse` transports |
| `REQUEST_TIMEOUT` | `30` | HTTP timeout (seconds) for portal API calls |
| `REQUEST_MAX_RETRIES` | `2` | Retries on transient failures (timeouts, connection errors, 429/5xx) with exponential backoff and `Retry-After` support |
| `RETRY_BACKOFF_SECONDS` | `0.5` | Base delay (seconds) for the retry backoff (`0.5s`, `1s`, `2s`...) |
| `MAX_DOWNLOAD_SIZE_MB` | `50` | Download cap for resource files used by the data tools |
| `DOWNLOAD_TIMEOUT` | `120` | Timeout (seconds) for resource downloads |
| `DEFAULT_LANGUAGE` | `fr` | Default output language for tool messages (`fr`, `ar`, or `en`); every search tool also accepts a per-call `language` argument |
| `ENABLE_GENERATIVE_UI` | `false` | Opt-in Generative UI provider: the LLM composes Prefab views at runtime in a Pyodide sandbox (needs Deno on the host). Adds 2 tools when enabled |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

## Docker

Build and run locally with Docker Compose:

```bash
docker compose up --build
```

The container serves the streamable HTTP transport on `0.0.0.0:${FASTMCP_PORT:-8000}` (`/mcp` + `/health`), with a built-in healthcheck. Configure via env vars in `docker-compose.yml` or a `.env` file next to it.

Manual build:

```bash
docker build -t datagouv-mcp-tn .
docker run -p 8000:8000 datagouv-mcp-tn
```

## Logging

All logs (app + uvicorn access logs) are emitted as single-line JSON for log aggregation pipelines, configured in `src/datagouv_mcp_tn/helpers/logging_config.py`. Verbosity is controlled by `LOG_LEVEL`.

## Security

The server includes multiple security layers (all configurable via `.env`):

| Layer | Implementation | Key Settings |
|-------|----------------|--------------|
| **Input validation** | FastMCP `strict_input_validation=True` + custom validators (`helpers/validators.py`) | `STRICT_INPUT_VALIDATION` |
| **Rate limiting** | `SlidingWindowRateLimitingMiddleware` (100 req/min default) | `RATE_LIMIT_ENABLED`, `RATE_LIMIT_MAX_REQUESTS`, `RATE_LIMIT_WINDOW_MINUTES` |
| **CORS** | Starlette `CORSMiddleware` with MCP-required headers | `CORS_ENABLED`, `CORS_ALLOWED_ORIGINS`, ... |
| **Host/Origin protection** | FastMCP built-in DNS rebinding guard (`host_origin_protection`) | `HOST_ORIGIN_PROTECTION`, `ALLOWED_HOSTS`, `ALLOWED_ORIGINS` |
| **Log sanitization** | Automatic masking of secrets (API keys, tokens, passwords) and PII (emails, IPs, user IDs) in all log records | `LOG_SANITIZATION_ENABLED` |

All security features are **enabled by default** with production-safe values. Override via `.env` as needed.

## Git hooks

[pre-commit](https://pre-commit.com) runs file hygiene checks and [ruff](https://docs.astral.sh/ruff/) lint + format:

```bash
uvx pre-commit install     # activate on git commit
uvx pre-commit run -a      # run on all files
```

## Dependencies

```bash
uv add <package>       # updates pyproject.toml + uv.lock automatically
uv remove <package>
```

Upgrade dependencies:

```bash
uv lock --upgrade && uv sync
```

## License

See [LICENSE](LICENSE).
