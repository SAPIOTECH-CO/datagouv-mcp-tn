# API Reference

## Base URL

```
https://<host>/mcp
```

## Transport

Le serveur MCP expose 3 transports :

| Transport | Endpoint | Usage |
|-----------|----------|-------|
| stdio | subprocess pipes | Clients locaux (Claude Desktop, opencode) |
| HTTP | `/mcp` | Production, clients distants |
| SSE | `/sse` | Legacy, compatibilité anciens clients |

## Tools

Tous les outils sont **read-only** (`readOnlyHint=true`) et acceptent un paramètre optionnel `portal` (défaut: `agridata`).

### search_datasets

Recherche de datasets par texte.

**Paramètres:**
- `query` (string, requis) : requête de recherche
- `page` (int, optionnel, défaut: 1) : numéro de page
- `page_size` (int, optionnel, défaut: 20, max: 100) : résultats par page
- `portal` (string, optionnel) : clé du portail
- `language` (string, optionnel) : `fr`, `ar`, ou `en`

**Retour:** Liste formatée de datasets avec IDs, titres, descriptions.

### suggest_datasets

Autocomplétion de titres de datasets.

**Paramètres:**
- `partial_query` (string, requis) : début de requête
- `size` (int, optionnel, défaut: 10) : nombre de suggestions
- `portal` (string, optionnel) : clé du portail

**Retour:** Liste de suggestions avec IDs et titres.

### get_dataset_info

Métadonnées complètes d'un dataset.

**Paramètres:**
- `dataset_id` (string, requis) : ID du dataset
- `portal` (string, optionnel) : clé du portail

**Retour:** Titre, description, organisation, license, tags, resources, et suggestion d'étape suivante.

### list_dataset_resources

Liste des ressources (fichiers) d'un dataset.

**Paramètres:**
- `dataset_id` (string, requis) : ID du dataset
- `portal` (string, optionnel) : clé du portail

**Retour:** Tableau des ressources avec ID, format, taille, URL.

### get_resource_info

Métadonnées d'une ressource spécifique.

**Paramètres:**
- `dataset_id` (string, requis) : ID du dataset parent
- `resource_id` (string, requis) : ID de la ressource
- `portal` (string, optionnel) : clé du portail

**Retour:** Titre, format, mimetype, taille, checksum, URL.

### search_organizations

Recherche d'organisations (producteurs de données).

**Paramètres:**
- `query` (string, requis) : requête de recherche
- `page` (int, optionnel, défaut: 1)
- `page_size` (int, optionnel, défaut: 20, max: 100)
- `portal` (string, optionnel) : clé du portail
- `language` (string, optionnel) : `fr`, `ar`, ou `en`

**Retour:** Liste formatée d'organisations.

### get_organization_info

Métadonnées complètes d'une organisation.

**Paramètres:**
- `organization_id` (string, requis) : ID de l'organisation
- `portal` (string, optionnel) : clé du portail

**Retour:** Nom, acronym, description, URL, metrics (membres, datasets).

### search_dataservices

Recherche de services de données (APIs publiées).

**Paramètres:**
- `query` (string, requis) : requête de recherche
- `page` (int, optionnel, défaut: 1)
- `page_size` (int, optionnel, défaut: 20, max: 100)
- `portal` (string, optionnel) : clé du portail
- `language` (string, optionnel) : `fr`, `ar`, ou `en`

**Retour:** Liste formatée de dataservices.

### get_dataservice_info

Métadonnées complètes d'un dataservice.

**Paramètres:**
- `dataservice_id` (string, requis) : ID du dataservice
- `portal` (string, optionnel) : clé du portail

**Retour:** Nom, description, base_api_url, organisation, endpoints.

### get_dataservice_openapi_spec

Récupération et résumé d'une spec OpenAPI.

**Paramètres:**
- `dataservice_id` (string, requis) : ID du dataservice
- `portal` (string, optionnel) : clé du portail

**Retour:** Titre, version, opérations (GET/POST...), endpoints.

### download_and_parse_resource

Téléchargement et analyse d'une ressource en mémoire.

**Paramètres:**
- `dataset_id` (string, requis) : ID du dataset
- `resource_id` (string, requis) : ID de la ressource
- `portal` (string, optionnel) : clé du portail

**Retour:**
- **Tabular (CSV, XLSX, ODS, JSON, GeoJSON)** : preview (rows, columns, extrait)
- **Non-tabular** : type (document, image, archive, markup, data), métadonnées (pages, dimensions...)

### query_resource_data

Filtrage/tri de données tabulaires en mémoire.

**Paramètres:**
- `dataset_id` (string, requis) : ID du dataset
- `resource_id` (string, requis) : ID de la ressource
- `columns` (string, optionnel) : colonnes à inclure (CSV)
- `filter_column` (string, optionnel) : colonne de filtrage
- `filter_op` (string, optionnel) : `eq`, `neq`, `contains`, `gt`, `lt`, `gte`, `lte`
- `filter_value` (string, optionnel) : valeur de filtrage
- `sort_by` (string, optionnel) : colonne de tri
- `sort_order` (string, optionnel) : `asc` ou `desc`
- `limit` (int, optionnel, défaut: 50, max: 200) : limite de résultats
- `offset` (int, optionnel, défaut: 0) : décalage pagination
- `portal` (string, optionnel) : clé du portail

**Retour:** Lignes filtrées/triées avec compteurs.

### get_metrics

Métriques d'usage pour un objet CKAN.

**Paramètres:**
- `object_type` (string, requis) : `dataset`, `organization`, `dataservice`, `reuse`
- `object_id` (string, requis) : ID de l'objet
- `portal` (string, optionnel) : clé du portail

**Retour:** Vues, followers, downloads, etc.

## Resources (URI Templates)

### ckan://config

Configuration serveur (JSON).

**Exemple:**
```json
{
  "default_portal": "agridata",
  "request_timeout": 30.0,
  "log_level": "INFO",
  "rate_limit_enabled": true
}
```

### ckan://schema

Schéma de référence API CKAN (abridged).

### ckan://portals

Registre de tous les portails connus.

### ckan://portals/{portal_key}/info

Détails d'un portail spécifique (nom, API URL, settings).

### ckan://portals/{portal_key}/api/docs

Documentation API CKAN pour un portail spécifique.

## Prompts

### explore_portal

```json
{
  "portal_key": "agridata"
}
```

Guide l'utilisateur pour explorer un portail CKAN.

### search_and_analyze

```json
{
  "topic": "population",
  "portal_key": "agridata"
}
```

Workflow de recherche et analyse de données sur un sujet.

### discover_portals

Compare les portails disponibles et leurs capacités.

### analyze_resource

```json
{
  "resource_hint": "csv",
  "portal_key": "agridata"
}
```

Guide d'analyse d'une ressource spécifique.

### workflow_assistant

Point d'entrée général pour naviguer dans les portails CKAN.

## Erreurs

Toutes les erreurs suivent le format MCP standard :

```json
{
  "code": -32600,
  "message": "Invalid request",
  "data": {
    "detail": "Additional error context"
  }
}
```

Codes courants :
- `-32600` : Invalid Request
- `-32601` : Method not found
- `-32602` : Invalid params
- `-32603` : Internal error
- `-32000` : CKAN API error (avec détail)
