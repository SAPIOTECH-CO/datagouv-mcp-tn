# Security Scan Report

**Date:** 2026-08-23  
**Branch:** main  
**Scanner versions:**
- Bandit: 1.9.4 (Python SAST)
- Trivy: 0.74.0 (Docker/filesystem scanner)

## SAST — Bandit

**Command:**
```bash
uv run bandit -r src/datagouv_mcp_tn -f json -o bandit-report.json
```

**Result:** ✅ **0 issues found**

| Severity | Count |
|----------|-------|
| HIGH | 0 |
| MEDIUM | 0 |
| LOW | 0 |

### Remediated issues

| Rule | File | Issue | Fix |
|------|------|-------|-----|
| B405 | `document_inspector.py` | `xml.etree.ElementTree` import | Replaced with `defusedxml.ElementTree` |
| B314 | `document_inspector.py` | `ET.fromstring` on untrusted XML | Replaced with `defusedxml.ElementTree.fromstring` |
| B112 | `document_inspector.py` | `try/except/continue` pattern | Added `# nosec B112` with justification |
| B101 | `document_inspector.py`, `file_parser.py` | `assert` used for validation | Added `# nosec B101` with justification |

## Docker — Trivy

**Command:**
```bash
trivy config --format json --output trivy-docker-report.json Dockerfile
```

**Result:** ✅ **0 misconfigurations found**

### Remediated issues

| Rule | Severity | Issue | Fix |
|------|----------|-------|-----|
| `container_image_user_as_root` | HIGH | Container runs as root | Added `USER appuser` to Dockerfile |

## Dependencies

**Command:**
```bash
trivy fs --format json --output trivy-deps-report.json .
```

**Result:** ✅ **0 vulnerabilities found** in Python dependencies (uv.lock)

## TLS Chain Repair (AIA fallback)

Some portal hosts (e.g. `catalog.data.gov.tn`) omit the intermediate
certificate from their TLS chain, breaking standard verification. Resource
downloads retry once by fetching the missing intermediates from the
certificate's AIA "CA Issuers" URLs (`helpers/tls_chain.py`).

Security properties:

- The assembled chain must still anchor to a root in the local trust store;
  a verified probe handshake gates every recovered context.
- Self-signed certificates discovered via AIA are never added as trust
  anchors (AIA is fetched over plain HTTP for some CAs).
- Failures degrade to the original error — verification is never skipped.
- Opt out with `TLS_AIA_FALLBACK=false`.

## Quality Gates Summary

| Gate | Tool | Status |
|------|------|--------|
| Lint | `ruff check` | ✅ Pass |
| Format | `ruff format` | ✅ Pass |
| Type check | `mypy` | ✅ Pass |
| Unit tests | `pytest` (268 tests) | ✅ Pass |
| Coverage | `pytest-cov` | ✅ 90% (target: >80%) |
| SAST | `bandit` | ✅ 0 issues |
| Docker scan | `trivy config` | ✅ 0 misconfigurations |
| Dependency scan | `trivy fs` | ✅ 0 vulnerabilities |

## Pre-commit Hooks

The following hooks run on every commit:

1. `check-yaml`, `check-toml` — config file validity
2. `end-of-file-fixer`, `trailing-whitespace` — hygiene
3. `check-added-large-files`, `check-merge-conflict` — anti-accidents
4. `ruff` — lint + import sorting
5. `ruff-format` — code formatting
6. `mypy` — static type checking
7. `bandit` — Python security linting

Install:
```bash
uvx pre-commit install
```

Run manually:
```bash
uvx pre-commit run -a
```
