# datagouv-mcp-tn

[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue)](https://www.python.org/)
[![FastMCP](https://img.shields.io/badge/FastMCP-3.4%2B-green)](https://gofastmcp.com/)
[![Coverage](https://img.shields.io/badge/coverage-90%25-brightgreen)](https://pytest-cov.readthedocs.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A generic Model Context Protocol (MCP) server for CKAN open data portals, focused on the Tunisian ecosystem. Built with [FastMCP](https://gofastmcp.com).

Supports **any CKAN portal** out of the box — add new data sources via environment variables without touching code.

## Prerequisites

- **Python 3.13+** (see `.python-version`)
- **[uv](https://docs.astral.sh/uv/)** — Python package & project manager

### Install uv (if not already installed)

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | ieu"
```

## Project setup

Clone the repository and install all dependencies into an isolated virtual environment:

```bash
git clone https://github.com/SAPIOTECH-CO/datagouv-mcp-tn.git
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
│   ├── server.py              # FastMCP instance + /health route + register_tools() + register_prompts()
│   ├── portals.py             # Dynamic portal registry (env discovery + built-in defaults)
│   ├── prompts/
│   │   └── dynamic.py         # Dynamic prompt templates with Context injection
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
│   ├── models/                 # Pydantic models for CKAN/uData payloads
│   │   ├── __init__.py         #   re-exports
│   │   ├── common.py           #   Pagination, Sort, FieldFilter, PaginationInfo
│   │   ├── dataset.py          #   Dataset, OrganizationRef, LicenseRef
│   │   ├── resource.py         #   Resource, Checksum
│   │   ├── dataservice.py      #   Dataservice, Endpoint
│   │   └── metrics.py          #   Metrics (+ per-object subtypes)
│   └── helpers/
│       ├── api_client.py       # async CKAN Action API client (httpx, multi-portal)
│       ├── config.py           # Settings (pydantic-settings, reads .env)
│       ├── context.py          # FastMCP Depends providers (default portal, language)
│       ├── file_parser.py      # in-memory CSV/XLS/XLSX/ODS/JSON/GeoJSON parsing (pandas)
│       ├── document_inspector.py # PDF/DOCX/PPTX/HTML(Scrapy)/XML/images/ZIP/KMZ summaries
│       ├── i18n.py             # AR/FR/EN message catalog for tool output
│       ├── logging.py          # logger + log_tool decorator
│       ├── logging_config.py   # structured JSON logging (uvicorn-aware)
│       ├── query_cleaner.py    # stop-word removal for search queries (FR/AR)
│       ├── resources.py        # MCP resource handlers (static + dynamic templates)
│       ├── mcp_tool_defaults.py  # READ_ONLY_EXTERNAL_API_TOOL annotations
│       └── validators.py       # Input validation/sanitization for all tool arguments
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

## Dynamic portals

The server ships with five built-in Tunisian CKAN portals (`data-gov-tn`, `industrie`, `culture`, `transport`, `agridata`). Add new portals without code changes by setting environment variables:

```bash
# Add a custom portal
PORTAL_MY_PORTAL_API_URL=https://catalog.example.com/api/3
PORTAL_MY_PORTAL_NAME=My Custom Portal
PORTAL_MY_PORTAL_CATALOG_URL=https://catalog.example.com
PORTAL_MY_PORTAL_API_KEY=optional-secret-key
PORTAL_MY_PORTAL_REQUIRES_AUTH=false
```

Optional per-portal overrides:

| Variable | Description |
| --- | --- |
| `PORTAL_<KEY>_NAME` | Display name (defaults to the key) |
| `PORTAL_<KEY>_CATALOG_URL` | UI catalog URL (derived from `API_URL` if omitted) |
| `PORTAL_<KEY>_DESCRIPTION` | Short description |
| `PORTAL_<KEY>_REQUIRES_AUTH` | `true` / `false` (default: `false`) |
| `PORTAL_<KEY>_API_KEY` | API key for authenticated portals |
| `PORTAL_<KEY>_REQUEST_TIMEOUT` | HTTP timeout in seconds (default: `30`) |
| `PORTAL_<KEY>_REQUEST_MAX_RETRIES` | Retries on transient failures (default: `2`) |
| `PORTAL_<KEY>_RETRY_BACKOFF_SECONDS` | Base delay for exponential backoff (default: `0.5`) |
| `PORTAL_<KEY>_DOWNLOAD_TIMEOUT` | Download timeout in seconds (default: `120`) |
| `PORTAL_<KEY>_MAX_DOWNLOAD_SIZE_MB` | Max download size in MB (default: `50`) |

The `<KEY>` is normalized to lowercase with dashes (e.g. `PORTAL_MY_PORTAL_API_URL` → key `my-portal`).

Set `DEFAULT_PORTAL_KEY` to change which portal tools target when no `portal` argument is provided.

## Prompts

The server exposes dynamic prompt templates via FastMCP's `@mcp.prompt` system. Prompts use `Context` injection to read runtime state (default portal, available portals) without hardcoding data sources.

Available prompts:

- `explore_portal` — guide the user through exploring a specific CKAN portal
- `search_and_analyze` — find datasets on a topic and analyze tabular resources
- `discover_portals` — compare available portals and their capabilities
- `analyze_resource` — inspect, parse, and query a specific resource file
- `workflow_assistant` — general entry point for navigating CKAN open data

Prompts are registered automatically on server startup (`server.py` → `register_prompts()`).

## Resources

Read portal metadata and API docs via dynamic resource templates:

| URI | Description |
| --- | --- |
| `ckan://config` | Server configuration (JSON) |
| `ckan://schema` | CKAN API schema reference (abridged) |
| `ckan://portals` | All known portals registry |
| `ckan://portals/{portal_key}/info` | Detailed info for a specific portal |
| `ckan://portals/{portal_key}/api/docs` | CKAN API docs for a specific portal |

## Tools

All tools are read-only (`readOnlyHint=True`) and query the CKAN Action API v3:

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
the formats actually found on CKAN portals (~80% of resources).

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
            except api_client.CKANError as e:
                return f"Error: {e}"
            return f"Result for {param}: {data}"
    ```

2. Register it in `src/datagouv_mcp_tn/tools/__init__.py` inside `register_tools()`.
3. If it needs a new API call, add a function in `helpers/api_client.py` instead of calling `_call_action` from the tool directly.
4. Add a test in `tests/test_tools.py` (mock at the `api_client` boundary, use the in-memory client).

## Adding a new prompt

1. Create a function in `src/datagouv_mcp_tn/prompts/dynamic.py` with the `@mcp.prompt` decorator:

    ```python
    @mcp.prompt
    async def my_prompt(ctx: Context, topic: str) -> str:
        \"\"\"Describe what this prompt helps the user accomplish.\"\"\"
        return f"Help the user explore data about: {topic}"
    ```

2. Register it in `register_prompts()` at the bottom of the same file.

## Production Deployment

### Docker Compose (production)

```bash
# Start with nginx reverse proxy + SSL
docker compose -f docker-compose.prod.yml up -d

# View logs
docker compose -f docker-compose.prod.yml logs -f
```

**Stack:**
- `datagouv-mcp-tn` : application (HTTP on :8000)
- `nginx` : reverse proxy + SSL termination (ports 80/443)
- `loki` : log aggregation (optional)
- `prometheus` : metrics (optional)

### Nginx SSL Configuration

1. Place your SSL certificates in `nginx/ssl/`:
```bash
nginx/ssl/
├── fullchain.pem
├── privkey.pem
└── chain.pem
```

2. Generate self-signed certs for testing:
```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/privkey.pem \
  -out nginx/ssl/fullchain.pem \
  -subj "/CN=localhost"
```

3. Configure DNS and reload nginx:
```bash
docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

### CI/CD

GitHub Actions pipeline (`.github/workflows/ci.yml`):
1. **Quality gates** : ruff, mypy, bandit
2. **Tests** : pytest with coverage + Codecov upload
3. **Build** : Docker image build + push to GHCR
4. **Scan** : Trivy vulnerability scan (SARIF → GitHub Security)
5. **Deploy** : SSH deployment to production server

## Testing

```bash
uv run pytest                              # all tests
uv run pytest tests/unit -v                # unit tests only
uv run pytest tests/integration -v         # integration + E2E tests
uv run pytest --cov=src/datagouv_mcp_tn    # with coverage report
```

### Test structure

| Directory | Scope | Description |
| --- | --- | --- |
| `tests/unit/` | Unit | One file per tool group + helpers, models, security, validators. API calls are mocked at the `api_client` boundary. |
| `tests/integration/` | Integration / E2E | API flow tests (retries, timeouts, SSL) and end-to-end scenario tests exercising full tool chains. |

### Coverage

Target: **> 80%** (currently ~90%). Run:

```bash
uv run pytest --cov=src/datagouv_mcp_tn --cov-report=term
```

### Quality gates

```bash
uv run ruff check src/ tests/        # lint + import sorting
uv run mypy src/datagouv_mcp_tn      # type checking
uvx pre-commit run -a                 # all hooks (ruff, mypy, yaml/toml checks)
```

Inspect the server interactively during development:

```bash
fastmcp dev main.py
```

## Configuration

Copy `.env.example` to `.env` and adjust. Key variables:

| Variable | Default | Description |
| --- | --- | --- |
| `DEFAULT_PORTAL_KEY` | `agridata` | Default portal for tools that don't specify `portal` |
| `PORTAL_<KEY>_API_URL` | *(none)* | Add a new CKAN portal dynamically |
| `PORTAL_<KEY>_API_KEY` | *(empty)* | API key for a specific portal |
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

### Security

All security features are **enabled by default** with production-safe values. Override via `.env` as needed.

### Application Security

| Layer | Implementation | Key Settings |
| --- | --- | --- |
| **Input validation** | FastMCP `strict_input_validation=True` + custom validators (`helpers/validators.py`) | `STRICT_INPUT_VALIDATION` |
| **Rate limiting** | `SlidingWindowRateLimitingMiddleware` (100 req/min default) | `RATE_LIMIT_ENABLED`, `RATE_LIMIT_MAX_REQUESTS`, `RATE_LIMIT_WINDOW_MINUTES` |
| **CORS** | Starlette `CORSMiddleware` with MCP-required headers | `CORS_ENABLED`, `CORS_ALLOWED_ORIGINS`, ... |
| **Host/Origin protection** | FastMCP built-in DNS rebinding guard (`host_origin_protection`) | `HOST_ORIGIN_PROTECTION`, `ALLOWED_HOSTS`, `ALLOWED_ORIGINS` |
| **Log sanitization** | Automatic masking of secrets (API keys, tokens, passwords) and PII (emails, IPs, user IDs) in all log records | `LOG_SANITIZATION_ENABLED` |

### SAST & Scanning

| Tool | Scope | Status |
| --- | --- | --- |
| **Bandit** | Python SAST | Configured in `.pre-commit-config.yaml` |
| **Trivy** | Docker image + filesystem | Used in CI/CD pipeline |
| **defusedxml** | XML parsing | Replaced `xml.etree.ElementTree` |

See `docs/security.md` for the full security scan report.

### Production Hardening

- **Docker**: Non-root user (`appuser`)
- **Nginx**: TLS 1.2/1.3, HSTS, security headers
- **Secrets**: Docker secrets for API keys
- **Network**: Internal bridge network, no exposed ports except 80/443

## Docker

Build and run locally with Docker Compose:

```bash
docker compose up --build
```

### Documentation

- [Architecture](docs/architecture.md) — Technical architecture overview
- [API Reference](docs/api_reference.md) — Complete tool, resource, and prompt reference
- [Client Setup](docs/client_setup.md) — Claude Desktop, OpenCode, ChatGPT, Cursor
- [Contribution Guide](docs/contribution.md) — Development workflow, testing, adding tools/portals
- [Security Report](docs/security.md) — Bandit/Trivy scans, remediated issues

The container serves the streamable HTTP transport on `0.0.0.0:${FASTMCP_PORT:-8000}` (`/mcp` + `/health`), with a built-in healthcheck. Configure via env vars in `docker-compose.yml` or a `.env` file next to it.

To add a custom portal in Docker, pass the `PORTAL_<KEY>_API_URL` environment variable:

```bash
docker compose up -d
docker compose exec datagouv-mcp-tn env | grep PORTAL_
# or in .env:
# PORTAL_MY_PORTAL_API_URL=https://catalog.example.com/api/3
```

Manual build:

```bash
docker build -t datagouv-mcp-tn .
docker run -p 8000:8000 datagouv-mcp-tn
```

## Logging

All logs (app + uvicorn access logs) are emitted as single-line JSON for log aggregation pipelines, configured in `src/datagouv_mcp_tn/helpers/logging_config.py`. Verbosity is controlled by `LOG_LEVEL`.

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
