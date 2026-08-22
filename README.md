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
├── tests/test_tools.py        # pytest suite (in-memory MCP client)
├── main.py                    # entry point (stdio by default, FASTMCP_TRANSPORT=http for HTTP)
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

Run the test suite:

```bash
uv run pytest            # all tests
uv run pytest -v         # verbose
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

## Building the MCP server (FastMCP quick start)

The server (`src/datagouv_mcp_tn/server.py`) exposes these tools against the uData API of data.gouv.tn:

| Tool | Description |
| --- | --- |
| `search_datasets` | Free-text search over datasets |
| `suggest_datasets` | Autocomplete dataset titles |
| `get_dataset_info` | Full metadata for one dataset |
| `list_dataset_resources` | Files inside a dataset (ID, format, size, URL) |
| `get_resource_info` | Detailed metadata for one resource |
| `search_organizations` | Search publishing organizations |
| `get_organization_info` | Full metadata for one organization |

A minimal FastMCP server looks like this:

```python
from fastmcp import FastMCP

mcp = FastMCP("DataGouv TN")

@mcp.tool
def hello(name: str) -> str:
    """Say hello."""
    return f"Hello, {name}!"

if __name__ == "__main__":
    mcp.run()               # stdio transport (default)
    # mcp.run(transport="http", port=8000)   # HTTP transport
```

Test it interactively with the built-in development inspector:

```bash
fastmcp dev main.py
```

Install it into your MCP client (e.g. Claude Desktop):

```bash
fastmcp install main.py
```

## License

See [LICENSE](LICENSE).
