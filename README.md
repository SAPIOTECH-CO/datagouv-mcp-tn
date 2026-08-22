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

```
datagouv-mcp-tn/
├── src/datagouv_mcp_tn/
│   ├── __init__.py        # exports the mcp instance
│   ├── config.py          # Settings (pydantic-settings, reads .env)
│   ├── client.py          # async uData API client (httpx)
│   └── server.py          # FastMCP server + tool definitions
├── tests/
│   └── test_tools.py      # pytest suite (in-memory MCP client)
├── main.py                # entry point
├── pyproject.toml         # project metadata + dependencies
├── uv.lock                # locked dependency versions (do not edit by hand)
├── .env.example           # copy to .env and fill in
└── .venv/                 # virtual environment (generated, git-ignored)
```

Run the project:

```bash
# with the venv activated
python main.py

# or without activating
uv run python main.py
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
| `get_dataset` | Full metadata for one dataset |
| `suggest_datasets` | Autocomplete dataset titles |
| `search_organizations` | Search publishing organizations |
| `get_organization` | Full metadata for one organization |

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
