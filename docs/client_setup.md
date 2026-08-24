# Client Setup Guide

This guide shows how to connect various MCP clients to `datagouv-mcp-tn`.

## Prerequisites

- The MCP server must be running (locally or remotely)
- For local (stdio) mode: Python 3.13+ and `uv` installed
- For remote (HTTP) mode: Server URL reachable from the client

## Claude Desktop

### Local (stdio)

1. Install the server:
```bash
git clone https://github.com/SAPIOTECH-CO/datagouv-mcp-tn.git
cd datagouv-mcp-tn
uv sync
```

2. Edit Claude Desktop config file:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "datagouv-tn": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/datagouv-mcp-tn",
        "run",
        "python",
        "main.py"
      ]
    }
  }
}
```

3. Restart Claude Desktop.

### Remote (HTTP)

```json
{
  "mcpServers": {
    "datagouv-tn": {
      "url": "https://your-server.com/mcp"
    }
  }
}
```

## OpenCode

### Local (stdio)

Add to your `opencode` config (e.g., `~/.config/opencode/config.yaml`):

```yaml
mcp:
  servers:
    datagouv-tn:
      command: "uv"
      args:
        - "--directory"
        - "/path/to/datagouv-mcp-tn"
        - "run"
        - "python"
        - "main.py"
```

### Remote (HTTP)

```yaml
mcp:
  servers:
    datagouv-tn:
      url: "https://your-server.com/mcp"
```

## ChatGPT (OpenAI)

ChatGPT supports MCP via the "Custom GPTs" feature.

1. Create a new GPT in ChatGPT
2. Go to "Configure" → "Connections"
3. Add a new MCP server:
   - **Name**: datagouv-tn
   - **URL**: `https://your-server.com/mcp`
4. Save and test the connection

## Cursor / Windsurf / Other IDEs

Most MCP-compatible IDEs support stdio or HTTP transports.

### stdio example

```json
{
  "mcpServers": {
    "datagouv-tn": {
      "command": "uv",
      "args": ["--directory", "/path/to/datagouv-mcp-tn", "run", "python", "main.py"]
    }
  }
}
```

### HTTP example

```json
{
  "mcpServers": {
    "datagouv-tn": {
      "url": "https://your-server.com/mcp"
    }
  }
}
```

## Direct HTTP API

For programmatic access without an MCP client, you can call the HTTP endpoint directly:

### List tools

```bash
curl -X POST https://your-server.com/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list"
  }'
```

### Call a tool

```bash
curl -X POST https://your-server.com/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "search_datasets",
      "arguments": {
        "query": "population",
        "portal": "agridata"
      }
    }
  }'
```

### Health check

```bash
curl https://your-server.com/health
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FASTMCP_TRANSPORT` | `stdio` | `stdio`, `http`, or `sse` |
| `FASTMCP_HOST` | `127.0.0.1` | Bind host for HTTP/SSE |
| `FASTMCP_PORT` | `8000` | Bind port for HTTP/SSE |
| `DEFAULT_PORTAL_KEY` | `agridata` | Default portal |
| `PORTAL_<KEY>_API_URL` | *(none)* | Add a new CKAN portal |
| `PORTAL_<KEY>_SSL_VERIFY` | `true` | SSL verification for portal |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

### Dynamic Portals

Add portals without code changes by setting environment variables:

```bash
PORTAL_MY_PORTAL_API_URL=https://catalog.example.com/api/3
PORTAL_MY_PORTAL_NAME=My Portal
PORTAL_MY_PORTAL_API_KEY=optional-key
```

## Troubleshooting

### SSL Certificate Errors

If you encounter SSL errors when connecting to a portal:

```bash
# Disable SSL verification for a specific portal
PORTAL_DATA_GOV_TN_SSL_VERIFY=false
```

Or in `.env`:
```env
PORTAL_DATA_GOV_TN_SSL_VERIFY=false
```

### Connection Refused

Ensure the server is running:
```bash
# Local stdio
uv run python main.py

# HTTP
FASTMCP_TRANSPORT=http uv run python main.py
```

### Timeout Errors

Increase the request timeout:
```env
REQUEST_TIMEOUT=60
DOWNLOAD_TIMEOUT=300
```

## Performance Tips

1. Use **HTTP transport** for production (lower latency than stdio)
2. Enable **caching** in nginx for static responses
3. Set appropriate `page_size` (max 100) to reduce API calls
4. Use `suggest_datasets` for autocomplete (lighter than full search)
5. Configure connection pooling via `REQUEST_MAX_RETRIES`
