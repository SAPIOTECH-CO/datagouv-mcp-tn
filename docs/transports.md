# Transport Options for datagouv-mcp-tn

## Server-Side Transports (set via TRANSPORT env var)

| Transport | Command | Use Case |
|-----------|---------|----------|
| **stdio** (default) | `uv run python -m datagouv_mcp_tn.server` | CLI/IDE integration (opencode, Claude Desktop, VS Code) |
| **sse** | `TRANSPORT=sse uv run python -m datagouv_mcp_tn.server` | Legacy streaming, backward compatibility |
| **http** | `TRANSPORT=http uv run python -m datagouv_mcp_tn.server` | Web clients, remote access, modern HTTP transport |

```bash
# stdio (default) - for opencode, Claude Desktop
uv run python -m datagouv_mcp_tn.server

# SSE - legacy streaming
TRANSPORT=sse uv run python -m datagouv_mcp_tn.server

# HTTP - web clients, remote access (recommended for new projects)
TRANSPORT=http uv run python -m datagouv_mcp_tn.server
```

## Client-Side Transports

FastMCP Client infers transport from URL pattern:

| Server URL Pattern | Client Transport | Use Case |
|--------------------|------------------|----------|
| `stdio` / local path | `StdioTransport` | Local subprocess (opencode, Claude Desktop) |
| `https://host/mcp` | `StreamableHttpTransport` | Modern HTTP transport (recommended) |
| `https://host/sse` | `SSETransport` | Legacy SSE streaming |
| `https://host/sse` with headers | `SSETransport` + auth | Authenticated legacy SSE |

### Client Code Examples

```python
from fastmcp import Client
from fastmcp.client.transports import StdioTransport, SSETransport, StreamableHttpTransport

# 1. Stdio (local subprocess) - opencode, Claude Desktop
client = Client("datagouv_mcp_tn")  # infers from mcp.json

# Explicit stdio with custom env
from fastmcp.client.transports import PythonStdioTransport
transport = PythonStdioTransport(
    command="uv",
    args=["run", "python", "-m", "datagouv_mcp_tn.server"],
    env={"DATA_GOUV_TN_API_URL": "https://data.gouv.tn/api/1"},
    cwd="/path/to/datagouv-mcp-tn",
)
client = Client(transport)

# 2. SSE Transport (legacy)
transport = SSETransport(url="http://localhost:8000/sse")
client = Client(transport)

# 3. HTTP Transport (modern, recommended)
transport = StreamableHttpTransport(url="http://localhost:8000/mcp")
client = Client(transport)

# 4. Remote server with auth
transport = StreamableHttpTransport(
    url="https://api.example.com/mcp",
    headers={"Authorization": "Bearer token"}
)
client = Client(transport)
```

## opencode Configuration

For opencode (uses stdio by default):

```json
{
  "mcp": {
    "datagouv-mcp-tn": {
      "type": "local",
      "command": ["uv", "run", "python", "-m", "datagouv_mcp_tn.server"],
      "cwd": "/path/to/datagouv-mcp-tn",
      "env": {
        "DATA_GOUV_TN_API_URL": "https://data.gouv.tn/api/1",
        "TRANSPORT": "stdio",
        "LOG_LEVEL": "INFO"
      },
      "enabled": true
    }
  }
}
```

## Running Different Transports

### For opencode (stdio) - Default
```bash
uv run python -m datagouv_mcp_tn.server
```

### For web clients (HTTP)
```bash
TRANSPORT=http uv run python -m datagouv_mcp_tn.server
# Runs on http://0.0.0.0:8000/mcp
```

### For legacy SSE clients (SSE)
```bash
TRANSPORT=sse uv run python -m datagouv_mcp_tn.server
# Runs on http://0.0.0.0:8000/sse
```

### With Docker
```bash
# stdio
docker run -e TRANSPORT=stdio datagouv-mcp-tn

# HTTP
docker run -p 8000:8000 -e TRANSPORT=http datagouv-mcp-tn

# SSE
docker run -p 8000:8000 -e TRANSPORT=sse datagouv-mcp-tn
```

## Transport Selection Guide

| Scenario | Recommended Transport |
|----------|----------------------|
| opencode / Claude Desktop / VS Code | `stdio` (default) |
| Web app / Remote client | `http` (StreamableHttpTransport) |
| Legacy SSE client | `sse` |
| Docker deployment | `http` (expose port 8000) |

**Note:** FastMCP 3.x recommends **HTTP transport** for new projects. SSE is legacy and only for backward compatibility.