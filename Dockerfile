FROM astral/uv:python3.13-trixie-slim

# Install needed apt packages
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Install dependencies (locked, reproducible)
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
COPY src ./src
COPY main.py ./
COPY .env.example ./
RUN uv sync --frozen --no-dev

ENV PYTHONUNBUFFERED=1 \
    FASTMCP_TRANSPORT=http \
    FASTMCP_HOST=0.0.0.0 \
    FASTMCP_PORT=8000

EXPOSE 8000

# Healthcheck uses the default port; override with --env FASTMCP_PORT if needed
HEALTHCHECK --interval=60s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

ENTRYPOINT ["uv", "run", "--no-sync"]
CMD ["python", "main.py"]
