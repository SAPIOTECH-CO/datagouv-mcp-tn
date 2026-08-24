# Data Retention & Deletion Policy

**Effective date:** 2026-08-24  
**Applies to:** `datagouv-mcp-tn` server deployments

## 1. Scope

This policy covers all data processed, stored, or transmitted by the MCP server:
- Server logs (application + access logs)
- Docker volumes (application logs, nginx logs, Loki/Prometheus data)
- Temporary files (in-memory buffers, download caches)
- Configuration and secrets

## 2. Data Classification

| Category | Sensitivity | Storage Location | Retention |
|----------|-------------|------------------|-----------|
| Server logs | Low | Docker volume `app-logs`, Loki | 30 days |
| Nginx access logs | Low | Docker volume `nginx-logs` | 30 days |
| Prometheus metrics | Low | Docker volume `prometheus-data` | 90 days |
| Loki logs | Low | Docker volume `loki-data` | 30 days |
| API keys / secrets | High | Docker secrets, environment variables | Until revoked |
| Downloaded resources | Medium | In-memory only (no disk) | Session lifetime |
| Query parameters | Low | Logs (sanitized) | 30 days |

## 3. Retention Periods

### 3.1 Logs
- Application logs: **30 days** retention
- Nginx access logs: **30 days** retention
- Logs are automatically rotated and deleted after retention period

### 3.2 Metrics
- Prometheus metrics: **90 days** retention
- Loki logs: **30 days** retention

### 3.3 Secrets
- API keys stored in Docker secrets: **Until explicitly revoked**
- No automatic expiration for secrets
- Rotation recommended every 90 days

### 3.4 Temporary Data
- Downloaded resources: **Session lifetime only** (in-memory, no disk)
- Parsed DataFrames: **Session lifetime only** (in-memory, no disk)
- HTTP client pools: **Server lifetime**

## 4. Deletion Procedures

### 4.1 Manual Deletion

```bash
# Stop services
docker compose -f docker-compose.prod.yml down

# Remove volumes (WARNING: deletes all data)
docker volume rm datagouv-mcp-tn_app-logs
docker volume rm datagouv-mcp-tn_nginx-logs
docker volume rm datagouv-mcp-tn_loki-data
docker volume rm datagouv-mcp-tn_prometheus-data

# Restart
docker compose -f docker-compose.prod.yml up -d
```

### 4.2 Automated Cleanup

Add to `docker-compose.prod.yml`:

```yaml
loki:
  image: grafana/loki:3.4
  command:
    - -config.file=/etc/loki/local-config.yaml
    - -retention.period=720h  # 30 days
```

Add log rotation to nginx:

```nginx
# In nginx/conf.d/default.conf
http {
    log_format compressed ...;
    access_log /var/log/nginx/access.log compressed;
    
    # Rotate logs daily, keep 30 days
    # (handled by logrotate in production)
}
```

## 5. Security Measures

### 5.1 Encryption at Rest
- Docker volumes are stored unencrypted by default
- For production, use encrypted volume drivers:
  ```bash
  # Example with Docker encrypted volumes plugin
  docker volume create --driver local \
    --opt o=encrypted \
    datagouv-mcp-tn_app-logs
  ```

### 5.2 Access Control
- Logs are only accessible to the `appuser` (non-root)
- Docker secrets are mounted read-only
- No SSH keys or credentials stored in code

### 5.3 Sanitization
- All logs are sanitized before writing (secrets + PII masked)
- See `helpers/logging_config.py` for sanitization rules

## 6. Compliance

### 6.1 Tunisian Data Protection Law (Loi n° 2004-63)
- The server does not collect personal data by default
- IP addresses in logs are considered metadata, not personal data
- Users are responsible for data they extract from portals

### 6.2 GDPR (if applicable)
- Right to erasure: Contact the server administrator
- Data minimization: Only necessary data is logged
- Storage limitation: Automatic deletion after retention period

## 7. Incident Response

In case of data breach:
1. Stop the server immediately
2. Preserve logs for forensic analysis
3. Rotate all API keys and secrets
4. Notify affected users within 72 hours
5. Document the incident and remediation steps

## 8. Review Cycle

This policy is reviewed annually or after any:
- Security incident
- Regulatory change
- Major architecture change

**Next review date:** 2027-08-24
