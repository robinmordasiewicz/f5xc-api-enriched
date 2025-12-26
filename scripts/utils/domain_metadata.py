"""Generate and manage domain metadata for CLI tool integration.

This utility provides programmatic assignment of metadata fields to domains
based on their characteristics and category, ensuring idempotent generation
suitable for CICD automation.
"""

from typing import Any

DOMAIN_METADATA = {
    # Infrastructure & Deployment
    "customer_edge": {
        "is_preview": False,
        "requires_tier": "Standard",
        "domain_category": "Infrastructure",
        "use_cases": [
            "Configure customer edge nodes",
            "Manage edge node registration and lifecycle",
            "Control module management and upgrades",
            "Configure network interfaces and USB policies",
        ],
        "related_domains": ["site", "cloud_infrastructure"],
    },
    "cloud_infrastructure": {
        "is_preview": False,
        "requires_tier": "Standard",
        "domain_category": "Infrastructure",
        "use_cases": [
            "Connect to cloud providers (AWS, Azure, GCP)",
            "Manage cloud credentials and authentication",
            "Configure cloud connectivity and elastic provisioning",
            "Link and manage cloud regions",
        ],
        "related_domains": ["site", "customer_edge"],
    },
    "container_services": {
        "is_preview": False,
        "requires_tier": "Advanced",
        "domain_category": "Infrastructure",
        "use_cases": [
            "Deploy Virtual Kubernetes (vK8s) namespaces",
            "Manage container workloads in multi-tenant environments",
            "Configure virtual sites and appliances",
            "Manage fleet configurations and deployments",
            "Handle workload orchestration",
        ],
        "related_domains": ["kubernetes", "service_mesh"],
    },
    "kubernetes": {
        "is_preview": False,
        "requires_tier": "Advanced",
        "domain_category": "Infrastructure",
        "use_cases": [
            "Manage enterprise Kubernetes clusters",
            "Configure pod security policies",
            "Manage container registries",
            "Integrate with external Kubernetes clusters",
        ],
        "related_domains": ["container_services", "service_mesh"],
    },
    "service_mesh": {
        "is_preview": False,
        "requires_tier": "Advanced",
        "domain_category": "Infrastructure",
        "use_cases": [
            "Configure service mesh connectivity",
            "Manage endpoint discovery and routing",
            "Configure NFV services",
            "Define application settings and types",
        ],
        "related_domains": ["kubernetes", "container_services", "virtual"],
    },
    "site": {
        "is_preview": False,
        "requires_tier": "Standard",
        "domain_category": "Infrastructure",
        "use_cases": [
            "Deploy F5 XC across cloud providers (AWS, Azure, GCP)",
            "Manage secure mesh sites",
            "Deploy voltstack sites for on-premises",
            "Integrate external Kubernetes clusters",
        ],
        "related_domains": ["cloud_infrastructure", "customer_edge"],
    },
    # Security - Core
    "api": {
        "is_preview": False,
        "requires_tier": "Advanced",
        "domain_category": "Security",
        "use_cases": [
            "Discover and catalog APIs",
            "Test API security and behavior",
            "Manage API credentials",
            "Define API groups and testing policies",
        ],
        "related_domains": ["waf", "network_security"],
    },
    "waf": {
        "is_preview": False,
        "requires_tier": "Advanced",
        "domain_category": "Security",
        "use_cases": [
            "Configure web application firewall rules",
            "Manage application security policies",
            "Enable enhanced firewall capabilities",
            "Configure protocol inspection",
        ],
        "related_domains": ["api", "network_security", "virtual"],
    },
    "bot_defense": {
        "is_preview": False,
        "requires_tier": "Advanced",
        "domain_category": "Security",
        "use_cases": [
            "Manage bot allowlists and defense policies",
            "Configure bot endpoints and infrastructure",
            "Integrate threat intelligence",
            "Manage mobile SDK for app protection",
        ],
        "related_domains": ["waf", "network_security"],
    },
    "network_security": {
        "is_preview": False,
        "requires_tier": "Advanced",
        "domain_category": "Security",
        "use_cases": [
            "Configure network firewall and ACL policies",
            "Manage NAT policies and port forwarding",
            "Configure policy-based routing",
            "Define network segments and policies",
            "Configure forward proxy policies",
        ],
        "related_domains": ["waf", "api", "network"],
    },
    # Security - Advanced
    "blindfold": {
        "is_preview": False,
        "requires_tier": "Advanced",
        "domain_category": "Security",
        "use_cases": [
            "Configure secret policies for encryption",
            "Manage sensitive data encryption",
            "Enforce data protection policies",
        ],
        "related_domains": ["client_side_defense", "certificates"],
    },
    "client_side_defense": {
        "is_preview": False,
        "requires_tier": "Advanced",
        "domain_category": "Security",
        "use_cases": [
            "Protect user data in transit",
            "Define sensitive data policies",
            "Manage device identification",
            "Configure data privacy controls",
        ],
        "related_domains": ["blindfold", "waf"],
    },
    "ddos": {
        "is_preview": False,
        "requires_tier": "Advanced",
        "domain_category": "Security",
        "use_cases": [
            "Configure DDoS protection policies",
            "Monitor and analyze DDoS threats",
            "Configure infrastructure protection",
        ],
        "related_domains": ["network_security", "virtual"],
    },
    "dns": {
        "is_preview": False,
        "requires_tier": "Standard",
        "domain_category": "Networking",
        "use_cases": [
            "Configure DNS load balancing",
            "Manage DNS zones and domains",
            "Configure DNS compliance policies",
            "Manage resource record sets (RRSets)",
        ],
        "related_domains": ["virtual", "network"],
    },
    "virtual": {
        "is_preview": False,
        "requires_tier": "Advanced",
        "domain_category": "Networking",
        "use_cases": [
            "Configure HTTP/TCP/UDP load balancers",
            "Manage origin pools and services",
            "Configure virtual hosts and routing",
            "Define rate limiter and service policies",
            "Manage geo-location-based routing",
            "Configure proxy and forwarding policies",
            "Manage malware protection and threat campaigns",
            "Configure health checks and endpoint monitoring",
        ],
        "related_domains": ["dns", "service_policy", "network"],
    },
    "network": {
        "is_preview": False,
        "requires_tier": "Advanced",
        "domain_category": "Networking",
        "use_cases": [
            "Configure BGP routing and ASN management",
            "Manage IPsec tunnels and IKE phases",
            "Configure network connectors and routes",
            "Manage SRv6 and subnetting",
            "Define segment connections and policies",
            "Configure IP prefix sets",
        ],
        "related_domains": ["virtual", "network_security", "dns"],
    },
    "cdn": {
        "is_preview": False,
        "requires_tier": "Advanced",
        "domain_category": "Networking",
        "use_cases": [
            "Configure CDN load balancing",
            "Manage content delivery network services",
            "Configure caching policies",
            "Manage data delivery and distribution",
        ],
        "related_domains": ["virtual"],
    },
    # Operations & Monitoring
    "observability": {
        "is_preview": False,
        "requires_tier": "Standard",
        "domain_category": "Operations",
        "use_cases": [
            "Configure synthetic monitoring",
            "Define monitoring and testing policies",
            "Manage observability dashboards",
        ],
        "related_domains": ["statistics", "support"],
    },
    "statistics": {
        "is_preview": False,
        "requires_tier": "Standard",
        "domain_category": "Operations",
        "use_cases": [
            "Access flow statistics and analytics",
            "Manage alerts and alerting policies",
            "View logs and log receivers",
            "Generate reports and graphs",
            "Track topology and service discovery",
            "Monitor status at sites",
        ],
        "related_domains": ["observability", "support"],
    },
    "support": {
        "is_preview": False,
        "requires_tier": "Standard",
        "domain_category": "Operations",
        "use_cases": [
            "Submit and manage support tickets",
            "Track customer support requests",
            "Access operational support documentation",
        ],
        "related_domains": ["statistics", "observability"],
    },
    # System & Management
    "authentication": {
        "is_preview": False,
        "requires_tier": "Standard",
        "domain_category": "Platform",
        "use_cases": [
            "Configure authentication mechanisms",
            "Manage OIDC and OAuth providers",
            "Configure SCIM user provisioning",
            "Manage API credentials and access",
            "Configure account signup policies",
        ],
        "related_domains": ["system", "users"],
    },
    "system": {
        "is_preview": False,
        "requires_tier": "Standard",
        "domain_category": "Platform",
        "use_cases": [
            "Manage tenant configuration",
            "Define RBAC policies and roles",
            "Manage namespaces and contacts",
            "Manage user accounts and groups",
            "Configure core system settings",
        ],
        "related_domains": ["authentication", "users", "admin"],
    },
    "users": {
        "is_preview": False,
        "requires_tier": "Standard",
        "domain_category": "Platform",
        "use_cases": [
            "Manage user accounts and tokens",
            "Configure user identification",
            "Manage user settings and preferences",
            "Configure implicit and known labels",
        ],
        "related_domains": ["system", "admin"],
    },
    # Platform & Integrations
    "bigip": {
        "is_preview": False,
        "requires_tier": "Advanced",
        "domain_category": "Platform",
        "use_cases": [
            "Manage BigIP F5 appliances",
            "Configure iRule scripts",
            "Manage data groups",
            "Integrate BigIP CNE",
        ],
        "related_domains": ["marketplace"],
    },
    "marketplace": {
        "is_preview": False,
        "requires_tier": "Advanced",
        "domain_category": "Platform",
        "use_cases": [
            "Access third-party integrations and add-ons",
            "Manage marketplace extensions",
            "Configure Terraform and external integrations",
            "Manage TPM policies",
        ],
        "related_domains": ["bigip", "admin"],
    },
    "nginx_one": {
        "is_preview": False,
        "requires_tier": "Advanced",
        "domain_category": "Platform",
        "use_cases": [
            "Manage NGINX One platform integrations",
            "Configure NGINX Plus instances",
            "Integrate NGINX configuration management",
        ],
        "related_domains": ["marketplace"],
    },
    # Advanced & Emerging
    "certificates": {
        "is_preview": False,
        "requires_tier": "Standard",
        "domain_category": "Security",
        "use_cases": [
            "Manage SSL/TLS certificates",
            "Configure trusted CAs",
            "Manage certificate revocation lists (CRL)",
            "Configure certificate manifests",
        ],
        "related_domains": ["blindfold", "system"],
    },
    "generative_ai": {
        "is_preview": True,
        "requires_tier": "Advanced",
        "domain_category": "AI",
        "use_cases": [
            "Access AI-powered features",
            "Configure AI assistant policies",
            "Enable flow anomaly detection",
            "Manage AI data collection",
        ],
        "related_domains": [],
    },
    "object_storage": {
        "is_preview": False,
        "requires_tier": "Advanced",
        "domain_category": "Platform",
        "use_cases": [
            "Manage object storage services",
            "Configure stored objects and buckets",
            "Manage storage policies",
        ],
        "related_domains": ["marketplace"],
    },
    "rate_limiting": {
        "is_preview": False,
        "requires_tier": "Advanced",
        "domain_category": "Networking",
        "use_cases": [
            "Configure rate limiter policies",
            "Manage policer configurations",
            "Control traffic flow and queuing",
        ],
        "related_domains": ["virtual", "network_security"],
    },
    "shape": {
        "is_preview": False,
        "requires_tier": "Advanced",
        "domain_category": "Security",
        "use_cases": [
            "Configure Shape Security policies",
            "Manage bot and threat prevention",
            "Configure SafeAP policies",
            "Enable threat recognition",
        ],
        "related_domains": ["bot_defense", "waf"],
    },
    # UI & Platform Infrastructure
    "admin": {
        "is_preview": False,
        "requires_tier": "Standard",
        "domain_category": "Platform",
        "use_cases": [
            "Configure administration console",
            "Manage navigation tiles and UI elements",
            "Configure static UI components",
        ],
        "related_domains": ["system", "users"],
    },
    "billing": {
        "is_preview": False,
        "requires_tier": "Standard",
        "domain_category": "Platform",
        "use_cases": [
            "Manage billing and subscription",
            "Configure payment methods",
            "Track usage and invoices",
            "Manage plan transitions",
            "Monitor quota usage",
        ],
        "related_domains": ["system", "users"],
    },
    "label": {
        "is_preview": False,
        "requires_tier": "Standard",
        "domain_category": "Platform",
        "use_cases": [
            "Manage resource labels and tagging",
            "Configure label policies",
            "Enable compliance tracking",
        ],
        "related_domains": ["system"],
    },
    "data_intelligence": {
        "is_preview": False,
        "requires_tier": "Standard",
        "domain_category": "Operations",
        "use_cases": [
            "Analyze security and traffic data",
            "Generate intelligent insights from logs",
            "Configure data analytics policies",
        ],
        "related_domains": ["statistics", "observability"],
    },
    "telemetry_and_insights": {
        "is_preview": False,
        "requires_tier": "Standard",
        "domain_category": "Operations",
        "use_cases": [
            "Collect and analyze telemetry data",
            "Generate actionable insights from metrics",
            "Configure telemetry collection policies",
        ],
        "related_domains": ["observability", "statistics"],
    },
    "threat_campaign": {
        "is_preview": False,
        "requires_tier": "Standard",
        "domain_category": "Security",
        "use_cases": [
            "Track and analyze threat campaigns",
            "Monitor active threats and attack patterns",
            "Configure threat intelligence integration",
        ],
        "related_domains": ["bot_defense", "ddos"],
    },
    "vpm_and_node_management": {
        "is_preview": False,
        "requires_tier": "Standard",
        "domain_category": "Platform",
        "use_cases": [
            "Manage Virtual Private Mesh (VPM) configuration",
            "Configure node lifecycle and management",
            "Monitor VPM and node status",
        ],
        "related_domains": ["site", "system"],
    },
}


def get_metadata(domain: str) -> dict[str, Any]:
    """Get metadata for a specific domain, including CLI metadata if available.

    Args:
        domain: The domain name

    Returns:
        Dict with is_preview, requires_tier, domain_category, use_cases, related_domains
        and optionally cli_metadata if available for the domain.
        Falls back to defaults if domain not explicitly configured.
    """
    metadata = DOMAIN_METADATA.get(
        domain,
        {
            "is_preview": False,
            "requires_tier": "Standard",
            "domain_category": "Other",
        },
    )

    # Add CLI metadata if available
    cli_metadata = get_cli_metadata(domain)
    if cli_metadata:
        metadata["cli_metadata"] = cli_metadata

    return metadata


def get_all_metadata() -> dict[str, dict[str, Any]]:
    """Get metadata for all configured domains."""
    return DOMAIN_METADATA.copy()


def calculate_complexity(path_count: int, schema_count: int) -> str:
    """Calculate domain complexity based on API surface area.

    Formula: score = (path_count * 0.4) + (schema_count * 0.6)
    Schema count weighted higher (60%) as data model complexity
    impacts code generation more than endpoint count.

    Args:
        path_count: Number of API endpoints/paths in the domain
        schema_count: Number of schemas/data models in the domain

    Returns:
        Complexity level: "simple" | "moderate" | "advanced"

    Examples:
        >>> calculate_complexity(2, 16)  # admin domain
        'simple'
        >>> calculate_complexity(36, 228)  # api domain
        'moderate'
        >>> calculate_complexity(164, 1248)  # virtual domain
        'advanced'
    """
    score = (path_count * 0.4) + (schema_count * 0.6)

    if score < 50:
        return "simple"
    if score < 150:
        return "moderate"
    return "advanced"


CLI_METADATA = {
    "virtual": {
        "quick_start": {
            "command": "curl $F5XC_API_URL/api/config/namespaces/default/http_loadbalancers -H 'Authorization: APIToken $F5XC_API_TOKEN'",
            "description": "List all HTTP load balancers in default namespace",
            "expected_output": "JSON array of load balancer objects with status",
        },
        "common_workflows": [
            {
                "name": "Create HTTP Load Balancer",
                "description": "Deploy basic HTTP load balancer with origin pool backend",
                "steps": [
                    {
                        "step": 1,
                        "command": "curl -X POST $F5XC_API_URL/api/config/namespaces/default/origin_pools -H 'Authorization: APIToken $F5XC_API_TOKEN' -H 'Content-Type: application/json' -d '{...pool_config...}'",
                        "description": "Create backend origin pool with target endpoints",
                    },
                    {
                        "step": 2,
                        "command": "curl -X POST $F5XC_API_URL/api/config/namespaces/default/http_loadbalancers -H 'Authorization: APIToken $F5XC_API_TOKEN' -H 'Content-Type: application/json' -d '{...lb_config...}'",
                        "description": "Create HTTP load balancer pointing to origin pool",
                    },
                ],
                "prerequisites": [
                    "Active namespace",
                    "Origin pool targets reachable",
                    "DNS domain configured",
                ],
                "expected_outcome": "Load balancer in Active status, traffic routed to origins",
            },
        ],
        "troubleshooting": [
            {
                "problem": "Load balancer shows Configuration Error status",
                "symptoms": [
                    "Status: Configuration Error",
                    "No traffic routing",
                    "Requests timeout",
                ],
                "diagnosis_commands": [
                    "curl $F5XC_API_URL/api/config/namespaces/default/http_loadbalancers/{name} -H 'Authorization: APIToken $F5XC_API_TOKEN'",
                    "Check origin_pool status and endpoint connectivity",
                ],
                "solutions": [
                    "Verify origin pool targets are reachable from edge",
                    "Check DNS configuration and domain propagation",
                    "Validate certificate configuration if using HTTPS",
                    "Review security policies not blocking traffic",
                ],
            },
        ],
        "icon": "⚖️",
    },
    "dns": {
        "quick_start": {
            "command": "curl $F5XC_API_URL/api/config/namespaces/default/dns_domains -H 'Authorization: APIToken $F5XC_API_TOKEN'",
            "description": "List all DNS domains configured in default namespace",
            "expected_output": "JSON array of DNS domain objects",
        },
        "common_workflows": [
            {
                "name": "Create DNS Domain",
                "description": "Configure DNS domain with load balancer backend",
                "steps": [
                    {
                        "step": 1,
                        "command": "Create load balancer endpoint first (virtual domain)",
                        "description": "Ensure target load balancer exists",
                    },
                    {
                        "step": 2,
                        "command": "curl -X POST $F5XC_API_URL/api/config/namespaces/default/dns_domains -H 'Authorization: APIToken $F5XC_API_TOKEN' -H 'Content-Type: application/json' -d '{...dns_config...}'",
                        "description": "Create DNS domain pointing to load balancer",
                    },
                ],
                "prerequisites": [
                    "DNS domain registered",
                    "Load balancer configured",
                    "SOA and NS records prepared",
                ],
                "expected_outcome": "DNS domain in Active status, queries resolving to load balancer",
            },
        ],
        "troubleshooting": [
            {
                "problem": "DNS queries not resolving",
                "symptoms": ["NXDOMAIN responses", "Timeout on DNS queries"],
                "diagnosis_commands": [
                    "curl $F5XC_API_URL/api/config/namespaces/default/dns_domains/{domain} -H 'Authorization: APIToken $F5XC_API_TOKEN'",
                    "nslookup {domain} @ns-server",
                ],
                "solutions": [
                    "Verify domain delegation to F5 XC nameservers",
                    "Check DNS domain configuration and backend load balancer status",
                    "Validate zone file and record configuration",
                ],
            },
        ],
        "icon": "🌐",
    },
    "api": {
        "quick_start": {
            "command": "curl $F5XC_API_URL/api/config/namespaces/default/api_catalogs -H 'Authorization: APIToken $F5XC_API_TOKEN'",
            "description": "List all API catalogs in default namespace",
            "expected_output": "JSON array of API catalog objects",
        },
        "common_workflows": [
            {
                "name": "Protect API with Security Policy",
                "description": "Discover and protect APIs with WAF security policies",
                "steps": [
                    {
                        "step": 1,
                        "command": "curl -X POST $F5XC_API_URL/api/config/namespaces/default/api_catalogs -H 'Authorization: APIToken $F5XC_API_TOKEN' -H 'Content-Type: application/json' -d '{...catalog_config...}'",
                        "description": "Create API catalog for API discovery and documentation",
                    },
                    {
                        "step": 2,
                        "command": "curl -X POST $F5XC_API_URL/api/config/namespaces/default/api_definitions -H 'Authorization: APIToken $F5XC_API_TOKEN' -H 'Content-Type: application/json' -d '{...api_config...}'",
                        "description": "Create API definition with security enforcement",
                    },
                ],
                "prerequisites": [
                    "API endpoints documented",
                    "Security policies defined",
                    "WAF rules configured",
                ],
                "expected_outcome": "APIs protected, violations logged and blocked",
            },
        ],
        "troubleshooting": [
            {
                "problem": "API traffic blocked by security policy",
                "symptoms": ["HTTP 403 Forbidden", "Requests rejected at edge"],
                "diagnosis_commands": [
                    "curl $F5XC_API_URL/api/config/namespaces/default/api_definitions/{api} -H 'Authorization: APIToken $F5XC_API_TOKEN'",
                    "Check security policy enforcement rules",
                ],
                "solutions": [
                    "Review API definition and security policy rules",
                    "Adjust rule sensitivity to reduce false positives",
                    "Add exception rules for legitimate traffic patterns",
                ],
            },
        ],
        "icon": "🔐",
    },
    "site": {
        "quick_start": {
            "command": "curl $F5XC_API_URL/api/config/namespaces/default/sites -H 'Authorization: APIToken $F5XC_API_TOKEN'",
            "description": "List all configured sites in default namespace",
            "expected_output": "JSON array of site objects with deployment status",
        },
        "common_workflows": [
            {
                "name": "Deploy AWS Cloud Site",
                "description": "Deploy F5 XC in AWS for traffic management",
                "steps": [
                    {
                        "step": 1,
                        "command": "curl -X POST $F5XC_API_URL/api/config/namespaces/default/cloud_credentials -H 'Authorization: APIToken $F5XC_API_TOKEN' -H 'Content-Type: application/json' -d '{...aws_credentials...}'",
                        "description": "Create cloud credentials for AWS access",
                    },
                    {
                        "step": 2,
                        "command": "curl -X POST $F5XC_API_URL/api/config/namespaces/default/sites -H 'Authorization: APIToken $F5XC_API_TOKEN' -H 'Content-Type: application/json' -d '{...site_config...}'",
                        "description": "Create site definition for AWS deployment",
                    },
                ],
                "prerequisites": [
                    "AWS account configured",
                    "Cloud credentials created",
                    "VPC and security groups prepared",
                ],
                "expected_outcome": "Site deployed in AWS, nodes connected and healthy",
            },
        ],
        "troubleshooting": [
            {
                "problem": "Site deployment fails",
                "symptoms": ["Status: Error", "Nodes not coming online", "Connectivity issues"],
                "diagnosis_commands": [
                    "curl $F5XC_API_URL/api/config/namespaces/default/sites/{site} -H 'Authorization: APIToken $F5XC_API_TOKEN'",
                    "Check site events and node status",
                ],
                "solutions": [
                    "Verify cloud credentials have required permissions",
                    "Check VPC and security group configuration",
                    "Review site logs for deployment errors",
                    "Ensure sufficient cloud resources available",
                ],
            },
        ],
        "icon": "🌍",
    },
    "system": {
        "quick_start": {
            "command": "curl $F5XC_API_URL/api/config/system/namespaces -H 'Authorization: APIToken $F5XC_API_TOKEN'",
            "description": "List all namespaces in the F5 XC system",
            "expected_output": "JSON array of namespace objects",
        },
        "common_workflows": [
            {
                "name": "Create Tenant Namespace",
                "description": "Create isolated namespace for tenant resources",
                "steps": [
                    {
                        "step": 1,
                        "command": "curl -X POST $F5XC_API_URL/api/config/system/namespaces -H 'Authorization: APIToken $F5XC_API_TOKEN' -H 'Content-Type: application/json' -d '{...namespace_config...}'",
                        "description": "Create namespace with appropriate quotas",
                    },
                    {
                        "step": 2,
                        "command": "curl -X POST $F5XC_API_URL/api/config/system/role_bindings -H 'Authorization: APIToken $F5XC_API_TOKEN' -H 'Content-Type: application/json' -d '{...role_config...}'",
                        "description": "Assign RBAC roles to namespace users",
                    },
                ],
                "prerequisites": [
                    "System admin access",
                    "User groups defined",
                    "Resource quotas planned",
                ],
                "expected_outcome": "Namespace created, users can access and manage resources",
            },
        ],
        "troubleshooting": [
            {
                "problem": "Users cannot access namespace resources",
                "symptoms": ["Permission denied errors", "Resources not visible"],
                "diagnosis_commands": [
                    "curl $F5XC_API_URL/api/config/system/namespaces/{ns} -H 'Authorization: APIToken $F5XC_API_TOKEN'",
                    "Check RBAC role bindings for namespace",
                ],
                "solutions": [
                    "Verify RBAC role bindings are correct",
                    "Check namespace quotas not exceeded",
                    "Review IAM policies for resource access",
                ],
            },
        ],
        "icon": "⚙️",
    },
}


def get_cli_metadata(domain: str) -> dict[str, Any] | None:
    """Get CLI metadata for a domain if available.

    Args:
        domain: The domain name

    Returns:
        Dict with quick_start, common_workflows, troubleshooting, icon
        or None if CLI metadata not available for this domain
    """
    return CLI_METADATA.get(domain)
