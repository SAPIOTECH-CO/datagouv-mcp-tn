# Architecture Technique

## Vue d'ensemble

`datagouv-mcp-tn` est un serveur **MCP (Model Context Protocol)** générique pour les portails CKAN, centré sur l'écosystème tunisien. Il expose des outils, prompts et ressources que les LLMs peuvent invoquer pour découvrir, explorer et analyser des données ouvertes.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Client MCP (Claude, ChatGPT, opencode...)     │
│                                 │                                       │
│                                 ▼                                       │
│                    ┌────────────────────────┐                          │
│                    │   Transport Layer      │                          │
│                    │   (stdio / HTTP / SSE) │                          │
│                    └───────────┬────────────┘                          │
│                                │                                       │
│                                ▼                                       │
│                    ┌────────────────────────┐                          │
│                    │   FastMCP Server       │                          │
│                    │   (mcp.py)             │                          │
│                    └───────────┬────────────┘                          │
│                                │                                       │
│            ┌───────────────────┼───────────────────┐                  │
│            │                   │                   │                  │
│            ▼                   ▼                   ▼                  │
│   ┌──────────────┐   ┌────────────────┐   ┌──────────────┐          │
│   │   Tools      │   │   Prompts      │   │   Resources  │          │
│   │ (13 tools)   │   │  (5 prompts)   │   │ (5 templates)│          │
│   └──────┬───────┘   └────────────────┘   └──────────────┘          │
│          │                                                          │
│          ▼                                                          │
│   ┌─────────────────────────────────────────────────────┐           │
│   │              Helpers Layer                          │           │
│   │  api_client │ config │ validators │ file_parser │     │           │
│   │  document_inspector │ i18n │ logging │ prefab_views│          │
│   └─────────────────────────────────────────────────────┘           │
│                                │                                       │
│                                ▼                                       │
│                    ┌────────────────────────┐                          │
│                    │   Portals Registry     │                          │
│                    │   (env discovery +     │                          │
│                    │    built-in defaults)  │                          │
│                    └───────────┬────────────┘                          │
│                                │                                       │
│          ┌─────────────────────┼─────────────────────┐               │
│          │                     │                     │               │
│          ▼                     ▼                     ▼               │
│   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐           │
│   │ data-gov-tn  │   │   industrie  │   │   agridata   │           │
│   │ (CKAN v3)    │   │   (CKAN v3)  │   │   (CKAN v3)  │           │
│   └──────────────┘   └──────────────┘   └──────────────┘           │
│                                 ...                                   │
└─────────────────────────────────────────────────────────────────────────┘
```

## Couches

### 1. Transport Layer
- **stdio** (default) : le client lance le serveur en subprocess
- **HTTP** : streamable HTTP sur `/mcp` (+ `/health`)
- **SSE** : legacy Server-Sent Events sur `/sse`

Sélectionné via `FASTMCP_TRANSPORT`.

### 2. FastMCP Server
- Instance `FastMCP` créée dans `server.py`
- Instructions globales pour guider les LLMs
- Enregistrement des tools, prompts, ressources via `register_*()`

### 3. Tools (13 outils)
Un fichier par outil dans `tools/` :

| Fichier | Outil | Rôle |
|---------|-------|------|
| `search_datasets.py` | `search_datasets` | Recherche textuelle de datasets |
| `suggest_datasets.py` | `suggest_datasets` | Autocomplétion de titres |
| `get_dataset_info.py` | `get_dataset_info` | Métadonnées complètes d'un dataset |
| `list_dataset_resources.py` | `list_dataset_resources` | Liste des fichiers d'un dataset |
| `get_resource_info.py` | `get_resource_info` | Métadonnées d'une ressource |
| `search_organizations.py` | `search_organizations` | Recherche d'organisations |
| `get_organization_info.py` | `get_organization_info` | Métadonnées d'une organisation |
| `search_dataservices.py` | `search_dataservices` | Recherche de services de données |
| `get_dataservice_info.py` | `get_dataservice_info` | Métadonnées d'un dataservice |
| `get_dataservice_openapi_spec.py` | `get_dataservice_openapi_spec` | Récupération + résumé d'une spec OpenAPI |
| `download_and_parse_resource.py` | `download_and_parse_resource` | Téléchargement + analyse (tabular, PDF, DOCX...) |
| `query_resource_data.py` | `query_resource_data` | Filtrage/tri de données tabulaires en mémoire |
| `get_metrics.py` | `get_metrics` | Métriques d'usage (vues, followers...) |

### 4. Prompts (5 prompts dynamiques)
- `explore_portal` : guide d'exploration d'un portail
- `search_and_analyze` : recherche + analyse de données
- `discover_portals` : comparaison des portails disponibles
- `analyze_resource` : workflow d'analyse d'une ressource
- `workflow_assistant` : point d'entrée général

Injectés via `@mcp.prompt` avec `Context` pour lire l'état runtime (portail par défaut, langue).

### 5. Resources (5 URI templates)
- `ckan://config` : configuration serveur
- `ckan://schema` : schéma API CKAN
- `ckan://portals` : registre des portails
- `ckan://portals/{key}/info` : détails d'un portail
- `ckan://portals/{key}/api/docs` : docs API d'un portail

### 6. Helpers
| Module | Rôle |
|--------|------|
| `api_client.py` | Client HTTP asynchrone CKAN Action API v3 (httpx, retry, multi-portal) |
| `config.py` | Settings via pydantic-settings (`.env`, env vars, per-portal overrides) |
| `context.py` | Providers `Depends` pour injection de dépendances (portail, langue) |
| `file_parser.py` | Parsing tabulaire en mémoire (CSV, XLSX, ODS, JSON, GeoJSON via pandas) |
| `document_inspector.py` | Inspection de fichiers non-tabulaires (PDF, DOCX, PPTX, HTML, XML, images, ZIP, KMZ) |
| `i18n.py` | Catalogue de messages multilingue (FR, AR, EN) |
| `logging.py` | Logger structuré + décorateur `@log_tool` |
| `logging_config.py` | Configuration JSON logging (uvicorn-aware) |
| `query_cleaner.py` | Nettoyage de requêtes (stop-words FR/AR) |
| `prefab_views.py` | Vues structurées enrichies (DataTable, métriques, Prefab apps) |
| `validators.py` | Validation/sanitization des arguments outils |
| `cors.py` | Middleware CORS configurable |
| `rate_limit.py` | Rate limiting sliding window |
| `mcp_tool_defaults.py` | Annotations par défaut (`readOnlyHint`, etc.) |

### 7. Portals Registry
- Découverte automatique via env vars `PORTAL_<KEY>_API_URL`
- 5 portails tunisiens par défaut (data-gov-tn, industrie, culture, transport, agridata)
- Per-portal settings : timeout, retries, SSL verify, API key

### 8. Models (Pydantic)
- `dataset.py` : Dataset, OrganizationRef, LicenseRef
- `resource.py` : Resource, Checksum
- `dataservice.py` : Dataservice, Endpoint
- `metrics.py` : Metrics + sous-types par objet
- `common.py` : PaginationInfo, FieldFilter, Sort

## Sécurité

| Couche | Implémentation |
|--------|---------------|
| Input validation | FastMCP `strict_input_validation` + validators custom |
| Rate limiting | `SlidingWindowRateLimitingMiddleware` |
| CORS | Starlette `CORSMiddleware` avec headers MCP requis |
| Host/Origin protection | DNS rebinding guard (FastMCP natif) |
| Log sanitization | Masquage automatique secrets + PII |
| SAST | Bandit (Python) + Trivy (Docker/deps) |
| XML sécurité | `defusedxml` au lieu de `xml.etree.ElementTree` |

## Déploiement

### Docker (production)
- `Dockerfile` : image minimale `astral/uv:python3.13-trixie-slim`, user non-root `appuser`
- `docker-compose.prod.yml` : app + nginx + loki + prometheus
- `nginx/conf.d/default.conf` : reverse proxy avec SSL (TLS 1.2/1.3), HSTS, security headers

### CI/CD (GitHub Actions)
- Lint + type check + security scan
- Tests avec coverage + upload Codecov
- Build + push Docker image (GitHub Container Registry)
- Scan image Trivy (SARIF → GitHub Security)
- Déploiement SSH automatisé

## Performance

- **Connexions HTTP** : pool par portail via `httpx.AsyncClient`
- **Retry** : backoff exponentiel + `Retry-After` (max 3 essais)
- **Downloads** : limites de taille configurables par portail
- **Parsing** : tout en mémoire, pas de fichiers temporaires
- **Prefab UI** : vues structurées pour DataTable, métriques (optionnel)
