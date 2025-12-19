#!/usr/bin/env python3
"""Tag generator for OpenAPI specifications.

Generates and assigns tags to operations based on path patterns,
aligned with F5 XC domain categorization.
"""

import re
from pathlib import Path
from typing import Any, ClassVar

import yaml


class TagGenerator:
    """Generates and assigns tags to OpenAPI operations.

    Assigns tags based on path patterns matching F5 XC domain categories.
    Also generates top-level tag metadata with descriptions.
    """

    # Tag definitions with descriptions (aligned with DOMAIN_PATTERNS in merge_specs.py)
    TAG_DEFINITIONS: ClassVar[dict[str, dict[str, Any]]] = {
        "API Security": {
            "description": "API security, discovery, testing, and protection operations",
            "patterns": [
                r"/api_sec/",
                r"/api_crawler/",
                r"/api_discovery/",
                r"/api_testing/",
                r"/api_group/",
                r"/sensitive_data/",
                r"/rule_suggestion/",
            ],
        },
        "Applications": {
            "description": "Application settings, types, and workload management",
            "patterns": [
                r"/app_setting/",
                r"/app_type/",
                r"/app_api_group/",
                r"/workload/",
            ],
        },
        "BIG-IP": {
            "description": "BIG-IP integration and management operations",
            "patterns": [
                r"/bigip/",
                r"/bigcne/",
            ],
        },
        "Billing": {
            "description": "Billing, invoices, payments, and usage tracking",
            "patterns": [
                r"/billing/",
                r"/invoice/",
                r"/payment/",
                r"/quota/",
                r"/usage/",
            ],
        },
        "CDN": {
            "description": "Content delivery network and caching operations",
            "patterns": [
                r"/cdn_loadbalancer/",
                r"/cdn_cache/",
            ],
        },
        "Configuration": {
            "description": "Global settings, labels, and configuration management",
            "patterns": [
                r"/global_setting/",
                r"/tenant_setting/",
                r"/known_label/",
                r"/implicit_label/",
            ],
        },
        "Identity": {
            "description": "Identity, access management, users, roles, and credentials",
            "patterns": [
                r"/namespace/",
                r"/user_group/",
                r"/user/",
                r"/user_identification/",
                r"/role/",
                r"/service_credential/",
                r"/api_credential/",
                r"/certificate/",
                r"/token/",
                r"/oidc_provider/",
                r"/scim/",
                r"/authentication/",
                r"/signup/",
                r"/contact/",
            ],
        },
        "Infrastructure": {
            "description": "Cloud sites, Kubernetes clusters, and infrastructure management",
            "patterns": [
                r"/cloud_credentials/",
                r"/aws_vpc_site/",
                r"/aws_tgw_site/",
                r"/azure_vnet_site/",
                r"/gcp_vpc_site/",
                r"/voltstack_site/",
                r"/securemesh_site/",
                r"/k8s_cluster/",
                r"/k8s_pod/",
                r"/virtual_k8s/",
                r"/ce_cluster/",
                r"/certified_hardware/",
                r"/registration/",
                r"/upgrade_status/",
                r"/module_management/",
            ],
        },
        "Infrastructure Protection": {
            "description": "DDoS protection and infrastructure security operations",
            "patterns": [
                r"/infraprotect/",
            ],
        },
        "Load Balancing": {
            "description": "HTTP, TCP, and UDP load balancer configuration",
            "patterns": [
                r"/http_loadbalancer/",
                r"/tcp_loadbalancer/",
                r"/udp_loadbalancer/",
                r"/healthcheck/",
                r"/origin_pool/",
                r"/proxy/",
            ],
        },
        "Networking": {
            "description": "Network policies, DNS, routing, and connectivity",
            "patterns": [
                r"/network_policy/",
                r"/network_firewall/",
                r"/network_interface/",
                r"/network_connector/",
                r"/virtual_network/",
                r"/site_mesh/",
                r"/dc_cluster/",
                r"/fleet/",
                r"/bgp/",
                r"/dns_zone/",
                r"/dns_domain/",
                r"/dns_load_balancer/",
                r"/dns_lb/",
                r"/dns_compliance/",
                r"/subnet/",
                r"/segment/",
                r"/cloud_connect/",
                r"/cloud_link/",
                r"/cloud_elastic/",
                r"/cloud_region/",
                r"/public_ip/",
                r"/nat_policy/",
                r"/address_allocator/",
                r"/advertise_policy/",
                r"/forwarding_class/",
                r"/ip_prefix_set/",
                r"/route/",
                r"/srv6/",
                r"/virtual_host/",
                r"/virtual_site/",
                r"/external_connector/",
                r"/policy_based_routing/",
            ],
        },
        "NGINX": {
            "description": "NGINX One management and configuration",
            "patterns": [
                r"/nginx/",
            ],
        },
        "Observability": {
            "description": "Logging, metrics, alerts, and monitoring operations",
            "patterns": [
                r"/log_receiver/",
                r"/global_log_receiver/",
                r"/log/",
                r"/metric/",
                r"/alert_policy/",
                r"/alert_receiver/",
                r"/alert/",
                r"/synthetic_monitor/",
                r"/monitor/",
                r"/trace/",
                r"/dashboard/",
                r"/report/",
                r"/flow_anomaly/",
                r"/flow/",
                r"/topology/",
                r"/graph/",
                r"/status_at_site/",
            ],
        },
        "Security": {
            "description": "WAF, firewall policies, bot defense, and access control",
            "patterns": [
                r"/app_firewall/",
                r"/waf/",
                r"/service_policy/",
                r"/rate_limiter/",
                r"/malicious/",
                r"/bot_defense/",
                r"/api_definition/",
                r"/enhanced_firewall/",
                r"/fast_acl/",
                r"/rbac_policy/",
                r"/secret_policy/",
                r"/secret_management/",
                r"/policer/",
                r"/protocol_policer/",
                r"/protocol_inspection/",
                r"/filter_set/",
                r"/trusted_ca/",
                r"/crl/",
                r"/geo_location/",
                r"/data_type/",
                r"/voltshare/",
            ],
        },
        "Service Mesh": {
            "description": "Service discovery, endpoints, and container management",
            "patterns": [
                r"/discovery/",
                r"/discovered_service/",
                r"/endpoint/",
                r"/cluster/",
                r"/container_registry/",
                r"/nfv_service/",
            ],
        },
        "Shape Security": {
            "description": "Client-side defense, device identification, and Shape security",
            "patterns": [
                r"/shape/",
                r"/client_side_defense/",
                r"/device_id/",
            ],
        },
        "Subscriptions": {
            "description": "Subscription management, marketplace, and add-on services",
            "patterns": [
                r"/subscription/",
                r"/addon_service/",
                r"/addon_subscription/",
                r"/marketplace/",
                r"/catalog/",
                r"/plan/",
                r"/navigation/",
            ],
        },
        "Tenant Management": {
            "description": "Multi-tenant configuration and management",
            "patterns": [
                r"/tenant_management/",
                r"/tenant_configuration/",
                r"/tenant_profile/",
                r"/tenant/",
                r"/child_tenant/",
                r"/allowed_tenant/",
                r"/managed_tenant/",
            ],
        },
        "VPN": {
            "description": "IPSec VPN, IKE configuration, and tunnel management",
            "patterns": [
                r"/ike1/",
                r"/ike2/",
                r"/ike_phase/",
                r"/tunnel",  # Matches /tunnel/ and /tunnels
            ],
        },
        "AI Assistant": {
            "description": "AI-powered assistant and automation operations",
            "patterns": [
                r"/ai_assistant/",
                r"/ai_data/",
            ],
        },
        "Other": {
            "description": "Miscellaneous operations",
            "patterns": [],  # Fallback for unmatched paths
        },
    }

    def __init__(self, config_path: Path | None = None) -> None:
        """Initialize with configuration from file.

        Args:
            config_path: Path to enrichment.yaml config.
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "enrichment.yaml"

        # Default configuration
        self._generate_metadata = True
        self._assign_to_operations = True
        self._tag_definitions = self.TAG_DEFINITIONS.copy()

        self._load_config(config_path)

        # Compile patterns for efficiency
        self._compiled_patterns: dict[str, list[re.Pattern]] = {}
        for tag_name, tag_info in self._tag_definitions.items():
            patterns = tag_info.get("patterns", [])
            self._compiled_patterns[tag_name] = [re.compile(p, re.IGNORECASE) for p in patterns]

        # Statistics tracking
        self._operations_tagged = 0
        self._tags_generated = 0

    def _load_config(self, config_path: Path) -> None:
        """Load configuration from YAML config."""
        if not config_path.exists():
            return

        with config_path.open() as f:
            config = yaml.safe_load(f) or {}

        tags_config = config.get("tags", {})
        self._generate_metadata = tags_config.get("generate_metadata", True)
        self._assign_to_operations = tags_config.get("assign_to_operations", True)

        # Override tag definitions if provided in config
        custom_tags = tags_config.get("tag_definitions", {})
        if custom_tags:
            for tag_name, tag_info in custom_tags.items():
                if tag_name in self._tag_definitions:
                    self._tag_definitions[tag_name].update(tag_info)
                else:
                    self._tag_definitions[tag_name] = tag_info

    def generate_tags(self, spec: dict[str, Any]) -> dict[str, Any]:
        """Apply tag generation to a specification.

        Args:
            spec: OpenAPI specification dictionary.

        Returns:
            Specification with tags assigned and metadata generated.
        """
        self._operations_tagged = 0
        self._tags_generated = 0

        result = spec.copy()

        # Step 1: Assign tags to operations
        if self._assign_to_operations:
            result = self._assign_operation_tags(result)

        # Step 2: Generate top-level tag metadata
        if self._generate_metadata:
            result = self._generate_tag_metadata(result)

        return result

    def _assign_operation_tags(self, spec: dict[str, Any]) -> dict[str, Any]:
        """Assign tags to operations based on path patterns."""
        result = spec.copy()
        paths = result.get("paths", {})

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            # Determine tag for this path
            tag = self._get_tag_for_path(path)

            for method, operation in path_item.items():
                # Skip non-operation keys like parameters, summary, etc.
                if method.lower() not in (
                    "get",
                    "post",
                    "put",
                    "patch",
                    "delete",
                    "head",
                    "options",
                    "trace",
                ):
                    continue

                if not isinstance(operation, dict):
                    continue

                # Get existing tags or create empty list
                existing_tags = operation.get("tags", [])

                # Only add tag if not already present
                if tag and tag not in existing_tags:
                    operation["tags"] = [tag, *existing_tags]
                    self._operations_tagged += 1

        return result

    def _get_tag_for_path(self, path: str) -> str | None:
        """Determine the appropriate tag for a path.

        Args:
            path: API path (e.g., "/api/v1/namespace/{namespace}/http_loadbalancer")

        Returns:
            Tag name or None if no match.
        """
        # Check each tag's patterns
        for tag_name, patterns in self._compiled_patterns.items():
            if tag_name == "Other":
                continue  # Skip fallback until the end

            for pattern in patterns:
                if pattern.search(path):
                    return tag_name

        # Return "Other" as fallback for unmatched paths
        return "Other"

    def _generate_tag_metadata(self, spec: dict[str, Any]) -> dict[str, Any]:
        """Generate top-level tags array with descriptions.

        Creates tag metadata for all tags that are used in operations.
        """
        result = spec.copy()

        # Collect all tags used in operations
        used_tags: set[str] = set()
        for path_item in result.get("paths", {}).values():
            if not isinstance(path_item, dict):
                continue
            for operation in path_item.values():
                if isinstance(operation, dict):
                    for tag in operation.get("tags", []):
                        used_tags.add(tag)

        # Also include any existing tags from the spec
        for tag in result.get("tags", []):
            if isinstance(tag, dict) and tag.get("name"):
                used_tags.add(tag["name"])

        # Generate tag metadata
        tags_metadata = []
        seen_tags = set()

        for tag_name in sorted(used_tags):
            if tag_name in seen_tags:
                continue
            seen_tags.add(tag_name)

            tag_entry = {"name": tag_name}

            # Add description from our definitions
            if tag_name in self._tag_definitions:
                description = self._tag_definitions[tag_name].get("description")
                if description:
                    tag_entry["description"] = description
                    self._tags_generated += 1

            tags_metadata.append(tag_entry)

        result["tags"] = tags_metadata
        return result

    def get_stats(self) -> dict[str, Any]:
        """Return statistics about tag generation."""
        return {
            "operations_tagged": self._operations_tagged,
            "tags_generated": self._tags_generated,
            "generate_metadata": self._generate_metadata,
            "assign_to_operations": self._assign_to_operations,
        }
