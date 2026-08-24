# Contribution Guide

## Getting Started

1. Fork the repository
2. Clone your fork:
```bash
git clone https://github.com/SAPIOTECH-CO/datagouv-mcp-tn.git
cd datagouv-mcp-tn
```

3. Install dependencies:
```bash
uv sync
```

4. Activate the virtual environment:
```bash
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate     # Windows
```

## Development Workflow

### 1. Create a branch

```bash
git checkout -b feat/my-new-feature
```

### 2. Make changes

Follow the existing architecture:
- One file per tool in `tools/`
- One file per model in `models/`
- Shared utilities in `helpers/`
- Register new tools in `tools/__init__.py`

### 3. Run quality checks

```bash
# Lint + format
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# Type check
uv run mypy src/datagouv_mcp_tn

# Security scan
uv run bandit -r src/datagouv_mcp_tn

# Tests + coverage
uv run pytest tests/unit tests/integration --cov=src/datagouv_mcp_tn
```

### 4. Run pre-commit hooks (recommended)

```bash
uvx pre-commit install
uvx pre-commit run -a
```

### 5. Commit and push

```bash
git add .
git commit -m "feat: add my new feature"
git push origin feat/my-new-feature
```

### 6. Create a Pull Request

Open a PR against `main` with:
- Clear description of changes
- Reference to related issues
- Screenshots/logs if applicable

## Adding a New Tool

1. Create `src/datagouv_mcp_tn/tools/<tool_name>.py`:
```python
from fastmcp import FastMCP
from datagouv_mcp_tn.helpers.logging import log_tool
from datagouv_mcp_tn.helpers.mcp_tool_defaults import READ_ONLY_EXTERNAL_API_TOOL

def register_my_tool(mcp: FastMCP) -> None:
    @mcp.tool(title="My Tool", annotations=READ_ONLY_EXTERNAL_API_TOOL)
    @log_tool
    async def my_tool(param: str) -> str:
        """Tool description."""
        return f"Result: {param}"
```

2. Register in `src/datagouv_mcp_tn/tools/__init__.py`:
```python
from datagouv_mcp_tn.tools.my_tool import register_my_tool

def register_tools(mcp: FastMCP) -> None:
    ...
    register_my_tool(mcp)
```

3. Add API client function in `helpers/api_client.py` if needed

4. Add tests in `tests/unit/test_tools_*.py`

## Adding a New Portal

Set environment variables (no code change needed):

```bash
PORTAL_MY_PORTAL_API_URL=https://catalog.example.com/api/3
PORTAL_MY_PORTAL_NAME=My Portal
PORTAL_MY_PORTAL_CATALOG_URL=https://catalog.example.com
PORTAL_MY_PORTAL_API_KEY=optional-key
PORTAL_MY_PORTAL_SSL_VERIFY=false  # if needed
```

## Testing

### Unit Tests

Located in `tests/unit/`:
- `test_tools_a.py` — search, suggest, dataset info, resources
- `test_tools_b.py` — organizations, dataservices, openapi
- `test_tools_c.py` — download, query, metrics
- `test_helpers.py` — api_client, validators, prefab views
- `test_models.py` — Pydantic models
- `test_security.py` — CORS, rate limiting, sanitization
- `test_document_inspector.py` — PDF, DOCX, PPTX, HTML, XML, images
- `test_file_parser.py` — CSV, XLSX, ODS, JSON parsing
- `test_context.py` — FastMCP dependency injection
- `test_portals.py` — dynamic portal registry
- `test_prompts.py` — prompt templates
- `test_resources.py` — MCP resource handlers
- `test_validators.py` — input validation

### Integration Tests

Located in `tests/integration/`:
- `test_api_flow.py` — API client flow, retries, timeouts, SSL
- `test_e2e.py` — end-to-end scenario tests

### Running Tests

```bash
# All tests
uv run pytest

# Unit tests only
uv run pytest tests/unit

# Integration tests only
uv run pytest tests/integration

# With coverage
uv run pytest --cov=src/datagouv_mcp_tn --cov-report=term

# Verbose
uv run pytest -v
```

### Writing Tests

- Mock at the `api_client` boundary
- Use the `mcp_client` fixture for tool tests
- Use `call_tool` helper to invoke tools and extract text
- Test both success and error paths

## Code Style

- **Line length**: 100 characters
- **Python version**: 3.13+
- **Type hints**: required (mypy strict)
- **Imports**: sorted with ruff (isort)
- **Docstrings**: required for public functions/classes
- **Error handling**: use `api_client.CKANError`, not bare `Exception`
- **Logging**: use `log_tool` decorator for tools

## Security

- Never commit secrets or API keys
- Use `.env` for local development (gitignored)
- Use Docker secrets for production
- Run `bandit` before committing
- Follow the principle of least privilege

## Reporting Issues

Please include:
- Python version (`python --version`)
- OS and version
- uv version (`uv --version`)
- Full error traceback
- Steps to reproduce

## License

By contributing, you agree that your contributions will be licensed under the project's license.
