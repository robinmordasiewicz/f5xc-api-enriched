# Domain Deprecation Guide

**Last Updated**: December 24, 2025
**Version Range**: v1.0.15 → v1.0.30
**Status**: Active deprecations with migration paths

## Overview

This guide documents all domain name changes, renames, and consolidations from v1.0.15 through v1.0.30. Each section provides migration guidance and implementation examples.

---

## Deprecated → Current Domain Mappings

### 1. Artificial Intelligence & Data Domains

#### `ai_intelligence` → `generative_ai` + `data_intelligence`

**Status**: 🔴 **DEPRECATED** (v1.0.24)
**Reason**: Domain split to separate AI service operations from data analysis capabilities
**Current Domains**:

- `generative_ai` (AI-powered features)
- `data_intelligence` (Data analysis and intelligence)

**Migration Path**:

| Previous Endpoint Pattern | New Domain | New Endpoint Pattern | Version |
|--------------------------|-----------|----------------------|---------|
| `/api/ai_intelligence/config/*` | `generative_ai` | `/api/config/generative_ai/*` | v1.0.24 |
| `/api/ai_intelligence/data/*` | `data_intelligence` | `/api/data-intelligence/*` | v1.0.24 |

**Migration Guide**:

```python
# BEFORE (v1.0.15)
import f5xc_api

ai_client = f5xc_api.client(domain='ai_intelligence')
config = ai_client.get_config('/api/ai_intelligence/config/policies')

# AFTER (v1.0.24+)
import f5xc_api

# For AI features
ai_client = f5xc_api.client(domain='generative_ai')
config = ai_client.get_config('/api/config/generative_ai/policies')

# For data analysis
data_client = f5xc_api.client(domain='data_intelligence')
analytics = data_client.get_data('/api/data-intelligence/analytics')
```

**API Clients**:

- **Python**: `f5-distributed-cloud-py` v2.0.0+
- **Go**: `f5-distributed-cloud-go` v2.1.0+
- **Terraform**: `terraform-provider-f5xc` v1.2.0+

**Deprecation Timeline**:

- ⚠️ v1.0.24: Both old and new paths accepted (soft deprecation)
- 🔴 v1.1.0: Old paths return 410 GONE with migration link
- ⛔ v2.0.0: Old paths completely removed

---

### 2. Security & Threat Prevention Domains

#### `shape_security` → `shape` + `client_side_defense` + `bot_defense`

**Status**: 🔴 **DEPRECATED** (v1.0.25)
**Reason**: Domain split to separate bot prevention, client protection, and API security
**Current Domains**:

- `shape` (Shape Security policies)
- `client_side_defense` (Client data protection)
- `bot_defense` (Bot management)

**Migration Path**:

| Previous | New Domain | New Path | Version |
|----------|-----------|----------|---------|
| `/api/shape_security/bot/*` | `bot_defense` | `/api/bot/policies/*` | v1.0.25 |
| `/api/shape_security/client/*` | `client_side_defense` | `/api/client_side_defense/*` | v1.0.25 |
| `/api/shape_security/config/*` | `shape` | `/api/shape/policies/*` | v1.0.25 |

**Migration Guide**:

```python
# BEFORE (v1.0.15)
security = f5xc_api.client(domain='shape_security')
bot_policy = security.get('/api/shape_security/bot/policies')
client_policy = security.get('/api/shape_security/client/config')

# AFTER (v1.0.25+)
bot_client = f5xc_api.client(domain='bot_defense')
bot_policy = bot_client.get('/api/bot/policies')

client_client = f5xc_api.client(domain='client_side_defense')
client_policy = client_client.get('/api/client_side_defense/config')

shape_client = f5xc_api.client(domain='shape')
shape_policy = shape_client.get('/api/shape/policies')
```

**Deprecation Timeline**:

- ⚠️ v1.0.25: Old paths accepted with deprecation headers
- 🔴 v1.1.0: Old paths redirect to new domains
- ⛔ v2.0.0: Old paths removed

---

### 3. Networking & Domain Management

#### `networking` → `network` + `dns` + `network_security`

**Status**: 🔴 **DEPRECATED** (v1.0.22)
**Reason**: Domain consolidation and reorganization for clearer functional separation
**Current Domains**:

- `network` (BGP, IPsec, routing)
- `dns` (DNS load balancing)
- `network_security` (Network firewall, NAT)

**Migration Path**:

| Previous | New Domain | New Path | Version |
|----------|-----------|----------|---------|
| `/api/networking/bgp/*` | `network` | `/api/network/bgp/*` | v1.0.22 |
| `/api/networking/dns/*` | `dns` | `/api/dns/zones/*` | v1.0.22 |
| `/api/networking/fw/*` | `network_security` | `/api/network_security/policies/*` | v1.0.22 |

**Migration Guide**:

```yaml
# BEFORE (v1.0.15)
networking:
  bgp_policy: /api/networking/bgp/policies
  dns_zone: /api/networking/dns/zones
  fw_policy: /api/networking/fw/policies

# AFTER (v1.0.22+)
network:
  bgp_policy: /api/network/bgp/policies
dns:
  zone: /api/dns/zones
network_security:
  fw_policy: /api/network_security/policies
```

**Deprecation Timeline**:

- ⚠️ v1.0.22: Old paths still functional
- 🔴 v1.1.0: Old paths with deprecation warnings
- ⛔ v2.0.0: Old paths removed

---

### 4. NGINX Integration

#### `nginx` → `nginx_one`

**Status**: 🟡 **SOFT DEPRECATION** (v1.0.26)
**Reason**: Clarify product name (NGINX One platform)
**Current Domain**: `nginx_one`

**Migration Path**:

| Previous | New | Version |
|----------|-----|---------|
| `/api/nginx/*` | `/api/nginx_one/*` | v1.0.26 |
| Domain: `nginx` | Domain: `nginx_one` | v1.0.26 |

**Migration Guide**:

```hcl
# BEFORE (Terraform v1.0.15)
resource "f5xc_nginx_config" "example" {
  domain = "nginx"
  # ...
}

# AFTER (Terraform v1.2.0+)
resource "f5xc_nginx_one_config" "example" {
  domain = "nginx_one"
  # ...
}
```

**Deprecation Timeline**:

- ⚠️ v1.0.26: Both `nginx` and `nginx_one` accepted
- 🔴 v1.1.0: `nginx` domain with deprecation notices
- ⛔ v2.0.0: `nginx` domain removed

---

### 5. Load Balancer & Virtual Server Consolidation

#### `virtual_server` → `virtual`

**Status**: 🔴 **DEPRECATED** (v1.0.18)
**Reason**: Consolidate load balancer operations under single `virtual` domain
**Current Domain**: `virtual`

**Migration Path**:

| Previous | New | Details | Version |
|----------|-----|---------|---------|
| `/api/config/virtual_servers/*` | `/api/config/loadbalancers/*` | HTTP/TCP/UDP LBs | v1.0.18 |
| `/api/config/app_loadbalancers/*` | `/api/config/loadbalancers/*` | Application LBs | v1.0.18 |
| Domain: `virtual_server` | Domain: `virtual` | Unified domain | v1.0.18 |

**Migration Guide**:

```python
# BEFORE (v1.0.15)
from f5xc.domains import virtual_server

vs = virtual_server.HttpLoadBalancer(
    name="my-lb",
    namespace="prod"
)

# AFTER (v1.0.18+)
from f5xc.domains import virtual

lb = virtual.HttpLoadBalancer(
    name="my-lb",
    namespace="prod"
)
```

**Deprecation Timeline**:

- ⚠️ v1.0.18: Old paths functional with warnings
- 🔴 v1.1.0: Old paths return 301 redirects
- ⛔ v2.0.0: Old paths removed

---

### 6. Content Delivery Network (CDN)

#### `cdn_and_content_delivery` → `cdn`

**Status**: 🔴 **DEPRECATED** (v1.0.21)
**Reason**: Simplified domain naming
**Current Domain**: `cdn`

**Migration Path**:

| Previous | New | Version |
|----------|-----|---------|
| `/api/cdn_and_content_delivery/*` | `/api/cdn/*` | v1.0.21 |
| Domain: `cdn_and_content_delivery` | Domain: `cdn` | v1.0.21 |

**Migration Guide**:

```bash
# BEFORE (v1.0.15)
curl -X GET https://api.volterra.io/api/cdn_and_content_delivery/distributions

# AFTER (v1.0.21+)
curl -X GET https://api.volterra.io/api/cdn/distributions
```

**Deprecation Timeline**:

- ⚠️ v1.0.21: Old paths still functional
- 🔴 v1.1.0: Old paths with deprecation headers
- ⛔ v2.0.0: Old paths removed

---

### 7. User & Account Management

#### `user_and_account_management` → `system` + `authentication` + `users`

**Status**: 🔴 **DEPRECATED** (v1.0.30)
**Reason**: Split large domain into functional components
**Current Domains**:

- `authentication` (Auth providers, credentials)
- `system` (Tenant, RBAC, namespaces)
- `users` (User accounts, tokens)

**Migration Path**:

| Previous | New Domain | New Path | Version |
|----------|-----------|----------|---------|
| `/api/user_and_account/auth/*` | `authentication` | `/api/auth/*` | v1.0.30 |
| `/api/user_and_account/tenant/*` | `system` | `/api/tenant/*` | v1.0.30 |
| `/api/user_and_account/users/*` | `users` | `/api/users/*` | v1.0.30 |

**Migration Guide**:

```yaml
# BEFORE (v1.0.15)
- domain: user_and_account_management
  paths:
    - /api/user_and_account/auth/oidc
    - /api/user_and_account/tenant/rbac
    - /api/user_and_account/users/credentials

# AFTER (v1.0.30+)
- domain: authentication
  paths:
    - /api/auth/oidc
- domain: system
  paths:
    - /api/tenant/rbac
- domain: users
  paths:
    - /api/users/credentials
```

**Deprecation Timeline**:

- ⚠️ v1.0.30: Old paths accepted
- 🔴 v1.1.0: Old paths with warnings
- ⛔ v2.0.0: Old paths removed

---

## Migration Strategies

### Strategy 1: Direct Endpoint Replacement

**Best For**: Simple API clients with specific endpoint usage

```python
# Mapping of old endpoints to new locations
ENDPOINT_MIGRATIONS = {
    "/api/ai_intelligence/": "/api/config/generative_ai/",
    "/api/shape_security/bot/": "/api/bot/policies/",
    "/api/networking/bgp/": "/api/network/bgp/",
}

def migrate_endpoint(old_path):
    for old, new in ENDPOINT_MIGRATIONS.items():
        if old in old_path:
            return old_path.replace(old, new)
    return old_path

# Usage
new_path = migrate_endpoint("/api/ai_intelligence/config/policies")
# Result: "/api/config/generative_ai/config/policies"
```

### Strategy 2: Client Wrapper

**Best For**: Application-level abstraction

```python
class LegacyClient:
    """Wrapper providing backward compatibility during migration."""

    def __init__(self, api_key, namespace):
        self.ai = f5xc_api.client(domain='generative_ai', api_key=api_key)
        self.data = f5xc_api.client(domain='data_intelligence', api_key=api_key)
        self.namespace = namespace

    def get_ai_config(self, path):
        """Deprecated: Use self.ai.get_config() instead."""
        return self.ai.get_config(path)

# Usage
client = LegacyClient(api_key="xxx", namespace="prod")
config = client.get_ai_config("/api/config/generative_ai/policies")
```

### Strategy 3: Gradle/Maven/NPM Configuration

**Best For**: Declarative infrastructure-as-code

```hcl
# Terraform: migrate domain references
resource "f5xc_load_balancer" "example" {
  name = "my-lb"

  # BEFORE: domain would be "virtual_server"
  # AFTER: domain is "virtual"
  domain = "virtual"
}
```

### Strategy 4: API Gateway/Proxy Rewrite

**Best For**: Large-scale infrastructure

```nginx
# NGINX configuration for API path rewriting during migration period
server {
    listen 443 ssl;
    server_name api.example.com;

    # Rewrite old ai_intelligence paths to new domains
    location ~ ^/api/ai_intelligence/(.+)$ {
        return 301 https://api.example.com/api/config/generative_ai/$1;
    }

    # Route to appropriate upstream
    location ~ ^/api/(.*?)/ {
        proxy_pass https://f5xc-api.volterra.io;
        proxy_set_header X-Migrated-From: legacy-domain;
    }
}
```

---

## Version-Specific Implementation

### For v1.0.15 Users (Current Stable)

**Action**: Plan migration timeline
**Tools**: Compare your API usage against deprecation mappings above

```bash
# Audit current API usage
grep -r "ai_intelligence\|shape_security\|networking" ./infrastructure
```

### For v1.0.22-v1.0.29 Users (Migration Window)

**Action**: Update API calls and clients progressively

```bash
# Check for deprecation warnings
curl -I https://api.example.com/api/ai_intelligence/config
# Response headers will include: Deprecation: true
```

### For v1.0.30+ Users (Post-Deprecation)

**Action**: All new deployments use new domain names
**Status**: Old endpoints returning warnings or errors

---

## Domain Statistics by Version

| Version | Total Domains | Changes | Status |
|---------|--------------|---------|--------|
| v1.0.15 | 47 | Baseline | Stable |
| v1.0.18 | 47 | `virtual_server` → `virtual` | Deprecated |
| v1.0.21 | 46 | CDN consolidation | Deprecated |
| v1.0.22 | 44 | Network split | Deprecated |
| v1.0.24 | 46 | AI domain split | Deprecated |
| v1.0.25 | 47 | Security split | Deprecated |
| v1.0.26 | 47 | NGINX rename | Soft-deprecated |
| v1.0.30 | 37 | User/Account split + consolidations | Current |

---

## Frequently Asked Questions

### Q: How do I know if I'm using deprecated domains?

**A**: Check your API calls for these domain names:

- `ai_intelligence` (deprecated in v1.0.24)
- `shape_security` (deprecated in v1.0.25)
- `networking` (deprecated in v1.0.22)
- `virtual_server` (deprecated in v1.0.18)
- `cdn_and_content_delivery` (deprecated in v1.0.21)
- `nginx` (soft-deprecated in v1.0.26)
- `user_and_account_management` (deprecated in v1.0.30)

### Q: When will old endpoints stop working?

**A**:

- **v1.0.30 - v1.1.x**: Deprecation warnings, old paths still functional
- **v1.1.0**: Redirect responses (301/302) with migration links
- **v2.0.0**: Complete removal, 410 GONE responses

### Q: Can I run both old and new code simultaneously?

**A**: Yes. During the soft-deprecation window (v1.0.x):

- Old code continues working with warnings
- New code can use new domains
- API accepts both patterns (useful for gradual migration)

### Q: What's the recommended migration order?

**A**:

1. `virtual_server` → `virtual` (v1.0.18) - Oldest, most critical
2. `cdn_and_content_delivery` → `cdn` (v1.0.21)
3. `networking` split (v1.0.22)
4. `ai_intelligence` split (v1.0.24)
5. `shape_security` split (v1.0.25)
6. `nginx` → `nginx_one` (v1.0.26)
7. `user_and_account_management` split (v1.0.30) - Most recent

### Q: Are there breaking changes in other areas?

**A**: Domain changes are the primary breaking changes. No breaking changes in:

- Authentication mechanisms
- Authorization/RBAC
- Data formats
- API response schemas

---

## Support & Resources

### Getting Help

- **Slack**: `#api-migrations` channel
- **GitHub Issues**: [f5xc-api-enriched/issues](https://github.com/robinmordasiewicz/f5xc-api-enriched/issues)
- **Documentation**: [F5 Distributed Cloud API Docs](https://docs.volterra.io/en/latest/api/)
- **API Reference**: [OpenAPI Specifications](https://github.com/robinmordasiewicz/f5xc-api-enriched)

### Migration Checklist

- [ ] Audit current code for deprecated domains
- [ ] Review applicable sections in this guide
- [ ] Test new domains in development environment
- [ ] Update production code before deprecation deadline
- [ ] Monitor API responses for deprecation warnings
- [ ] File issues for migration blockers

---

## Document Changes

| Date | Version | Change |
|------|---------|--------|
| 2025-12-24 | 1.0 | Initial deprecation guide creation |

---

**Generated**: December 24, 2025
**Next Review**: March 24, 2026 (v1.1.0 release)
**Maintainer**: Claude Code (f5xc-api-enriched project)
