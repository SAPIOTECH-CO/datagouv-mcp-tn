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
│   │   └── get_organization_info.py
│   └── helpers/
│       ├── api_client.py      # async uData API client (httpx)
│       ├── config.py          # Settings (pydantic-settings, reads .env)
│       ├── logging.py         # logger + log_tool decorator
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

Typical flow: `search_datasets` → `get_dataset_info` → `list_dataset_resources` → `get_resource_info`.

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
| `LOG_LEVEL` | `INFO` | Logging verbosity |

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
