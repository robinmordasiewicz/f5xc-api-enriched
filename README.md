# f5xc-api-enriched

F5 Distributed Cloud API enrichment tools and utilities.

## Subscription & Licensing Architecture

F5 Distributed Cloud uses a **Plan-Based Access Control (PBAC)** system with addon services organized into subscription tiers.

### Subscription Tiers

F5 XC uses two subscription tiers:

| Tier | Description |
|------|-------------|
| **STANDARD** | Base tier with core functionality |
| **ADVANCED** | Premium tier with advanced features |

> **Note**: The API enum `schemaAddonServiceTierType` includes deprecated values (`BASIC`, `PREMIUM`) for backward compatibility. Only `STANDARD` and `ADVANCED` are active tiers. See [Issue #164](https://github.com/robinmordasiewicz/f5xc-api-enriched/issues/164) for deprecation tracking.

### Tier Identification Methods

#### AddonServiceTierType Enum

Schema: `schemaAddonServiceTierType`

```json
{
  "tier": "STANDARD"
}
```

Active values: `STANDARD`, `ADVANCED`

Deprecated values: `NO_TIER`, `BASIC`, `PREMIUM`

#### Addon Service Naming Convention

Pattern: `f5xc_{feature}_{tier}`

| Service | Standard | Advanced |
|---------|----------|----------|
| WAAP | `f5xc_waap_standard` | `f5xc_waap_advanced` |
| SecureMesh | `f5xc_securemesh_standard` | `f5xc_securemesh_advanced` |
| CDN | `f5xc_content_delivery_network_standard` | `f5xc_content_delivery_network_advanced` |
| AppStack | `f5xc_appstack_standard` | - |
| BigIP iRule | `f5xc_big_ip_irule_standard` | - |
| BigIP Utilities | `f5xc_bigip_utilities_standard` | - |
| Delegated Access | `f5xc_delegated_access_standard` | - |
| Site Management | `f5xc_site_management_standard` | - |
| Synthetic Monitoring | `f5xc_synthetic_monitoring_standard` | - |
| Web App Scanning | `f5xc_web_app_scanning_standard` | - |

### Subscription Specifications (18 Files)

**Core Subscription & Plan Management (6 specs)**:

| Spec | Purpose |
|------|---------|
| `subscription.ves-swagger.json` | Main Subscribe/Unsubscribe operations |
| `pbac.plan.ves-swagger.json` | Plan definition and listing |
| `billing.plan_transition.ves-swagger.json` | Plan migration workflow |
| `usage.plan.ves-swagger.json` | Usage plans and billing |
| `usage.subscription.ves-swagger.json` | Subscription details APIs |
| `billing.payment_method.ves-swagger.json` | Payment method management |

**Addon Infrastructure (2 specs)**:

| Spec | Purpose |
|------|---------|
| `pbac.addon_service.ves-swagger.json` | Addon service definitions with tier enum |
| `pbac.addon_subscription.ves-swagger.json` | Addon subscription lifecycle |

**Service-Specific Subscriptions (10 specs)**:

| Spec | Service |
|------|---------|
| `ai_data.bfdp.subscription.ves-swagger.json` | Bot Defense Data Intelligence |
| `shape.client_side_defense.subscription.ves-swagger.json` | Client-side Defense |
| `shape.data_delivery.subscription.ves-swagger.json` | Data Delivery/CDN |
| `dns_zone.subscription.ves-swagger.json` | DNS Zone |
| `malware_protection.subscription.ves-swagger.json` | Malware Protection |
| `shape.mobile_app_shield.subscription.ves-swagger.json` | Mobile App Shield |
| `shape.mobile_integrator.subscription.ves-swagger.json` | Mobile Integrator |
| `nginx.one.subscription.ves-swagger.json` | NGINX One |
| `observability.subscription.ves-swagger.json` | Observability |
| `shape.bot_defense.subscription.ves-swagger.json` | Bot Defense |

### API Endpoints for Tier Detection

| Endpoint | Purpose | Returns |
|----------|---------|---------|
| `GET /api/web/namespaces/system/usage_plans/current` | Current plan | Plan with `usage_plan_type` |
| `GET /api/web/namespaces/system/usage_plans/custom_list` | All available plans | `ListUsagePlansRsp` |
| `GET /api/web/namespaces/system/addon_services/{name}/activation-status` | Single service status | `tier` + `state` |
| `GET /api/web/namespaces/system/addon_services/{name}/all-activation-status` | All tiers status | Multi-tier status |
| `GET /api/web/namespaces/{ns}/quota/usage` | Quota limits | Tier-specific limits |
| `GET /api/web/custom/namespaces/shared/addon_services/{name}` | Service details | Full addon spec |

### PBAC Access Control States

| State | Description |
|-------|-------------|
| `AS_AC_NONE` | Not subscribed or pending |
| `AS_AC_ALLOWED` | Access granted (tier permits) |
| `AS_AC_PBAC_DENY` | Plan doesn't include this service |
| `AS_AC_PBAC_DENY_UPGRADE_PLAN` | Requires plan upgrade |
| `AS_AC_PBAC_DENY_CONTACT_SALES` | Contact sales required |
| `AS_AC_PBAC_DENY_AS_AC_EOL` | Service end of life |

### Subscription States

**Addon Service States**:

| State | Description |
|-------|-------------|
| `AS_PENDING` | Pending activation |
| `AS_SUBSCRIBED` | Successfully subscribed |
| `AS_ERROR` | Error state |

**Subscription Lifecycle States**:

| State | Description |
|-------|-------------|
| `SUBSCRIPTION_PENDING` | Awaiting enablement |
| `SUBSCRIPTION_ENABLED` | Active |
| `SUBSCRIPTION_DISABLE_PENDING` | Disable in progress |
| `SUBSCRIPTION_DISABLED` | Disabled |

### Plan Types

| Type | Description |
|------|-------------|
| `FREE` | Freemium (no payment required) |
| `INDIVIDUAL` | Single-user paid plan |
| `TEAM` | Multi-user paid plan |
| `ORGANIZATION` | Enterprise paid plan |

### Tenant Types

| Type | Description |
|------|-------------|
| `FREEMIUM` | Free tenant (no custom domain) |
| `ENTERPRISE` | Enterprise tenant (has custom domain) |

#### TenantType to Subscription Tier Mapping

The `tenant_type` field in the API response maps to subscription tier access:

| TenantType | Subscription Tier | Feature Access |
|------------|-------------------|----------------|
| `FREEMIUM` | **Standard** | Base tier features only |
| `ENTERPRISE` | **Advanced** | Full feature access including advanced capabilities |

**API Endpoint**: `GET /api/web/namespaces/system/usage_plans/current`

**Response field**: `plans[].tenant_type`

> **Implementation Note**: When determining subscription tier from API responses, map `ENTERPRISE` → "Advanced" and `FREEMIUM` → "Standard". For unknown values, default to "Standard" for fail-safe behavior. See [xcsh implementation](https://github.com/robinmordasiewicz/xcsh/blob/main/pkg/subscription/client.go#L411-L422) for reference.

### Activation Types

| Type | Description |
|------|-------------|
| `self_activation` | User can subscribe directly |
| `partially_managed_activation` | Requires some backend intervention |
| `managed_activation` | Complete manual SRE intervention |

### Plan Transition Methods

| Method | Description |
|--------|-------------|
| `TRANSITION_METHOD_SUPPORT` | Requires support ticket |
| `TRANSITION_METHOD_WIZARD` | Self-service UI wizard |
| `TRANSITION_METHOD_RECREATE` | Requires tenant recreation |

### Feature Comparison (Standard vs Advanced)

| Capability | Standard | Advanced |
|------------|----------|----------|
| Basic functionality | Yes | Yes |
| Service networking | Yes | Yes |
| CDN, DNS, App Stack | Yes | Yes |
| API discovery & protection | No | Yes |
| Behavioral bot mitigation | No | Yes |
| Layer 7 DDoS mitigation | No | Yes |
| Advanced multi-cloud networking | No | Yes |

### Quota/Limits by Tier

Tiers differ in resource limits (from `default_quota`):

- **Object limits**: Virtual hosts, origin pools, etc.
- **API rate limits**: Requests per second
- **Resource limits**: Bandwidth, request counts

### Marketplace Integrations

**Azure Marketplace** (`marketplace.xc_saas`):

- `SignupXCSaaS` - Process signup from Azure entitlement
- Token-based provisioning with HMAC security

**AWS Marketplace** (`marketplace.aws_account`):

- AWS-specific integration for marketplace purchases

### Subscription Flow

1. **Signup** - User selects plan (determines included/allowed services)
2. **Plan Assignment** - Plan defines `included_services` (auto-subscribed) and `allowed_services`
3. **Subscribe** - Create addon_subscription for desired services
4. **Activation** - Based on activation type (self/partial/managed)
5. **Access Control** - PBAC validates tier access at runtime
6. **Catalog View** - Filtered by user's plan showing access status

### References

- [F5 Product Comparison](https://www.f5.com/products/get-f5/compare)
- AddonServiceTierType enum: `pbac.addon_service` spec
- PBAC access states: `pbac.catalog` spec
