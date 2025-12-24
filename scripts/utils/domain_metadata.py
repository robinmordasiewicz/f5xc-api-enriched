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
        "requires_tier": "Professional",
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
        "requires_tier": "Professional",
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
        "requires_tier": "Professional",
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
        "requires_tier": "Professional",
        "domain_category": "Security",
        "use_cases": [
            "Discover and catalog APIs",
            "Test API security and behavior",
            "Manage API credentials",
            "Define API groups and testing policies",
        ],
        "related_domains": ["application_firewall", "network_security"],
    },
    "application_firewall": {
        "is_preview": False,
        "requires_tier": "Professional",
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
        "requires_tier": "Professional",
        "domain_category": "Security",
        "use_cases": [
            "Manage bot allowlists and defense policies",
            "Configure bot endpoints and infrastructure",
            "Integrate threat intelligence",
            "Manage mobile SDK for app protection",
        ],
        "related_domains": ["application_firewall", "network_security"],
    },
    "network_security": {
        "is_preview": False,
        "requires_tier": "Professional",
        "domain_category": "Security",
        "use_cases": [
            "Configure network firewall and ACL policies",
            "Manage NAT policies and port forwarding",
            "Configure policy-based routing",
            "Define network segments and policies",
            "Configure forward proxy policies",
        ],
        "related_domains": ["application_firewall", "api", "network"],
    },
    # Security - Advanced
    "blindfold": {
        "is_preview": False,
        "requires_tier": "Enterprise",
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
        "requires_tier": "Professional",
        "domain_category": "Security",
        "use_cases": [
            "Protect user data in transit",
            "Define sensitive data policies",
            "Manage device identification",
            "Configure data privacy controls",
        ],
        "related_domains": ["blindfold", "application_firewall"],
    },
    "ddos": {
        "is_preview": False,
        "requires_tier": "Enterprise",
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
        "requires_tier": "Professional",
        "domain_category": "Networking",
        "use_cases": [
            "Configure HTTP/TCP/UDP load balancers",
            "Manage origin pools and services",
            "Configure virtual hosts and routing",
            "Define rate limiter policies",
            "Manage geo-location-based routing",
            "Configure proxy and forwarding policies",
        ],
        "related_domains": ["dns", "service_policy", "network"],
    },
    "virtual_server": {
        "is_preview": False,
        "requires_tier": "Professional",
        "domain_category": "Networking",
    },
    "network": {
        "is_preview": False,
        "requires_tier": "Professional",
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
        "requires_tier": "Enterprise",
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
    "system": {
        "is_preview": False,
        "requires_tier": "Standard",
        "domain_category": "Platform",
        "use_cases": [
            "Manage tenant configuration",
            "Configure authentication and OIDC",
            "Define RBAC policies and roles",
            "Manage namespaces and contacts",
            "Configure SCIM integration",
        ],
        "related_domains": ["users", "admin"],
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
        "requires_tier": "Enterprise",
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
        "requires_tier": "Professional",
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
        "requires_tier": "Professional",
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
        "requires_tier": "Enterprise",
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
        "requires_tier": "Professional",
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
        "requires_tier": "Professional",
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
        "requires_tier": "Enterprise",
        "domain_category": "Security",
        "use_cases": [
            "Configure Shape Security policies",
            "Manage bot and threat prevention",
            "Configure SafeAP policies",
            "Enable threat recognition",
        ],
        "related_domains": ["bot_defense", "application_firewall"],
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
}


def get_metadata(domain: str) -> dict[str, Any]:
    """Get metadata for a specific domain.

    Args:
        domain: The domain name

    Returns:
        Dict containing:
        - is_preview: Whether domain is in preview/beta
        - requires_tier: Minimum subscription tier (Standard, Professional, Enterprise)
        - domain_category: Functional category (Infrastructure, Security, Networking, etc.)
        - use_cases: List of primary use cases
        - related_domains: List of related/complementary domains

        Falls back to defaults if domain not explicitly configured.
    """
    return DOMAIN_METADATA.get(
        domain,
        {
            "is_preview": False,
            "requires_tier": "Standard",
            "domain_category": "Other",
            "use_cases": [],
            "related_domains": [],
        },
    )


def get_all_metadata() -> dict[str, dict[str, Any]]:
    """Get metadata for all configured domains."""
    return DOMAIN_METADATA.copy()
