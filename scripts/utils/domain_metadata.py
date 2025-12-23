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
    },
    "cloud_infrastructure": {
        "is_preview": False,
        "requires_tier": "Standard",
        "domain_category": "Infrastructure",
    },
    "container_services": {
        "is_preview": False,
        "requires_tier": "Professional",
        "domain_category": "Infrastructure",
    },
    "kubernetes": {
        "is_preview": False,
        "requires_tier": "Professional",
        "domain_category": "Infrastructure",
    },
    "service_mesh": {
        "is_preview": False,
        "requires_tier": "Professional",
        "domain_category": "Infrastructure",
    },
    "site": {
        "is_preview": False,
        "requires_tier": "Standard",
        "domain_category": "Infrastructure",
    },
    # Security - Core
    "api": {
        "is_preview": False,
        "requires_tier": "Professional",
        "domain_category": "Security",
    },
    "application_firewall": {
        "is_preview": False,
        "requires_tier": "Professional",
        "domain_category": "Security",
    },
    "bot_and_threat_defense": {
        "is_preview": False,
        "requires_tier": "Professional",
        "domain_category": "Security",
    },
    "network_security": {
        "is_preview": False,
        "requires_tier": "Professional",
        "domain_category": "Security",
    },
    # Security - Advanced
    "blindfold": {
        "is_preview": False,
        "requires_tier": "Enterprise",
        "domain_category": "Security",
    },
    "client_side_defense": {
        "is_preview": False,
        "requires_tier": "Professional",
        "domain_category": "Security",
    },
    "ddos": {
        "is_preview": False,
        "requires_tier": "Enterprise",
        "domain_category": "Security",
    },
    "dns": {
        "is_preview": False,
        "requires_tier": "Standard",
        "domain_category": "Networking",
    },
    "virtual": {
        "is_preview": False,
        "requires_tier": "Professional",
        "domain_category": "Networking",
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
    },
    "cdn": {
        "is_preview": False,
        "requires_tier": "Enterprise",
        "domain_category": "Networking",
    },
    # Operations & Monitoring
    "observability": {
        "is_preview": False,
        "requires_tier": "Standard",
        "domain_category": "Operations",
    },
    "statistics": {
        "is_preview": False,
        "requires_tier": "Standard",
        "domain_category": "Operations",
    },
    "support": {
        "is_preview": False,
        "requires_tier": "Standard",
        "domain_category": "Operations",
    },
    # System & Management
    "system": {
        "is_preview": False,
        "requires_tier": "Standard",
        "domain_category": "Platform",
    },
    "users": {
        "is_preview": False,
        "requires_tier": "Standard",
        "domain_category": "Platform",
    },
    # Platform & Integrations
    "bigip": {
        "is_preview": False,
        "requires_tier": "Enterprise",
        "domain_category": "Platform",
    },
    "marketplace": {
        "is_preview": False,
        "requires_tier": "Professional",
        "domain_category": "Platform",
    },
    "nginx_one": {
        "is_preview": False,
        "requires_tier": "Professional",
        "domain_category": "Platform",
    },
    # Advanced & Emerging
    "certificates": {
        "is_preview": False,
        "requires_tier": "Standard",
        "domain_category": "Security",
    },
    "generative_ai": {
        "is_preview": True,
        "requires_tier": "Enterprise",
        "domain_category": "AI",
    },
    "object_storage": {
        "is_preview": False,
        "requires_tier": "Professional",
        "domain_category": "Platform",
    },
    "rate_limiting": {
        "is_preview": False,
        "requires_tier": "Professional",
        "domain_category": "Networking",
    },
    "shape": {
        "is_preview": False,
        "requires_tier": "Enterprise",
        "domain_category": "Security",
    },
    # UI & Platform Infrastructure
    "admin_console_and_ui": {
        "is_preview": False,
        "requires_tier": "Standard",
        "domain_category": "Platform",
    },
    "billing_and_usage": {
        "is_preview": False,
        "requires_tier": "Standard",
        "domain_category": "Platform",
    },
    "label": {
        "is_preview": False,
        "requires_tier": "Standard",
        "domain_category": "Platform",
    },
}


def get_metadata(domain: str) -> dict[str, Any]:
    """Get metadata for a specific domain.

    Args:
        domain: The domain name

    Returns:
        Dict with is_preview, requires_tier, domain_category
        Falls back to defaults if domain not explicitly configured.
    """
    return DOMAIN_METADATA.get(
        domain,
        {
            "is_preview": False,
            "requires_tier": "Standard",
            "domain_category": "Other",
        },
    )


def get_all_metadata() -> dict[str, dict[str, Any]]:
    """Get metadata for all configured domains."""
    return DOMAIN_METADATA.copy()
