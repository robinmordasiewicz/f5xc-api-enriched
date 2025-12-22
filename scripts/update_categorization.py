#!/usr/bin/env python3
"""Idempotent script to update API endpoint categorization from 23 to 31 functional domains.

This script safely updates the DOMAIN_PATTERNS dictionary in merge_specs.py with the new
comprehensive categorization structure. It can be run multiple times safely:
- Creates backup of original before modification
- Validates changes before committing
- Provides detailed reporting on categorization changes
- Exits cleanly on errors

Usage:
    python3 scripts/update_categorization.py [--validate-only] [--backup-dir DIR]

Options:
    --validate-only      Check categorization without modifying files
    --backup-dir DIR     Directory to store backups (default: .backups)
    --verbose            Show detailed categorization analysis
"""

import argparse
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# New 31-category domain patterns (data-driven from API analysis)
# Enhanced with complete coverage of all 270 spec files
NEW_DOMAIN_PATTERNS = {
    # ===== A. Infrastructure & Deployment (5 categories) =====
    "site_management": [
        r"aws_vpc_site",
        r"aws_tgw_site",
        r"azure_vnet_site",
        r"gcp_vpc_site",
        r"voltstack_site",
        r"securemesh_site",
        r"k8s_cluster",
        r"virtual_k8s",
        r"virtual_site",
        r"\.site\.",
    ],
    "cloud_infrastructure": [
        r"cloud_credentials",
        r"cloud_connect",
        r"cloud_elastic",
        r"cloud_link",
        r"cloud_region",
        r"certified_hardware",
    ],
    "vpm_and_node_management": [
        r"registration",
        r"module_management",
        r"upgrade_status",
        r"maintenance_status",
        r"usb_policy",
        r"network_interface",
    ],
    "kubernetes_and_orchestration": [
        r"k8s_cluster",
        r"k8s_pod_security",
        r"virtual_appliance",
        r"workload",
        r"container_registry",
        r"\.cluster\.",
    ],
    "service_mesh": [
        r"site_mesh",
        r"virtual_network",
        r"virtual_host",
        r"endpoint",
        r"nfv_service",
        r"fleet",
        r"discovery",
        r"app_setting",
        r"app_type",
    ],
    # ===== B. Security - Core (4 categories) =====
    "app_firewall": [
        r"app_firewall",
        r"app_security",
        r"waf",
        r"protocol_inspection",
        r"enhanced_firewall",
    ],
    "api_security": [
        r"api_sec\.",
        r"api_crawler",
        r"api_discovery",
        r"api_testing",
        r"api_group",
        r"code_base_integration",
        r"api_credential",
        r"api_definition",
    ],
    "bot_and_threat_defense": [
        r"bot_defense",
        r"bot_allowlist",
        r"bot_endpoint",
        r"bot_infrastructure",
        r"bot_network",
        r"mobile_sdk",
        r"mobile_base",
        r"threat_intelligence",
    ],
    "network_security": [
        r"network_firewall",
        r"network_policy",
        r"nat_policy",
        r"forward_proxy",
        r"fast_acl",
        r"policy_based_routing",
        r"service_policy",
        r"segment",
        r"filter_set",
    ],
    # ===== C. Security - Advanced (3 categories) =====
    "data_and_privacy_security": [
        r"sensitive_data_policy",
        r"data_privacy",
        r"client_side_defense",
        r"device_id",
        r"data_type",
    ],
    "infrastructure_protection": [
        r"infraprotect",
    ],
    "secops_and_incident_response": [
        r"secret_management",
        r"secret_policy",
        r"ticket_tracking",
        r"malicious_user",
    ],
    # ===== D. Application Delivery (2 categories) =====
    "virtual_server": [
        # Core Standard-tier load balancers (views. prefix prevents CDN/DNS match)
        r"views\.http_loadbalancer",
        r"views\.tcp_loadbalancer",
        r"views\.udp_loadbalancer",
        # Supporting resources
        r"views\.origin_pool",
        r"(?<!dns_lb)\.healthcheck\.ves",  # Matches healthcheck specs, excludes dns_lb_health_check via negative lookbehind
        r"\.virtual_host\.ves",
        r"^[^.]*\.route\.ves",  # Excludes operate.route, traceroute
        r"views\.rate_limiter_policy",  # LB-specific (not general rate_limiter)
        r"views\.proxy\.ves",
        r"views\.forward_proxy_policy",
    ],
    "dns_and_domain_management": [
        r"dns_load_balancer",  # Moved from virtual_server (explicit)
        r"dns_zone",
        r"dns_domain",
        r"dns_compliance",
        r"dns_lb_",  # Keeps dns_lb_health_check, dns_lb_pool
        r"rrset",
    ],
    # ===== E. Connectivity & Networking (2 categories) =====
    "network_connectivity": [
        r"bgp_routing",
        r"bgp",
        r"bgp_asn",
        r"route",
        r"tunnel",
        r"segment_connection",
        r"network_connector",
        r"ip_prefix_set",
        r"advertise_policy",
        r"subnet",
        r"srv6",
        r"address_allocator",
        r"public_ip",
        r"forwarding_class",
        r"dc_cluster_group",
    ],
    "vpn_and_encryption": [
        r"ike1",
        r"ike2",
        r"ike_phase",
    ],
    # ===== F. Content & Performance (1 category) =====
    "cdn_and_content_delivery": [
        r"cdn_loadbalancer",  # Moved from virtual_server
        r"cdn_cache",  # Moved from virtual_server
        r"cdn_",  # Other CDN resources
        r"data_delivery",
    ],
    # ===== G. Observability (3 categories) =====
    "observability_and_analytics": [
        r"synthetic_monitor",
        r"alert_policy",
        r"alert_receiver",
        r"alert",
        r"log_receiver",
        r"global_log_receiver",
        r"log",
        r"report",
        r"observability\.",
        r"brmalerts",
    ],
    "telemetry_and_insights": [
        r"graph",
        r"topology",
        r"flow",
        r"discovered_service",
        r"status_at_site",
    ],
    "platform_operations": [
        r"operate\.",
        r"customer_support",
    ],
    # ===== H. Enterprise & Administration (3 categories) =====
    "tenant_and_identity_management": [
        r"tenant_management",
        r"tenant",
        r"namespace",
        r"user_group",
        r"user",
        r"rbac_policy",
        r"role",
        r"authentication",
        r"oidc_provider",
        r"scim",
        r"signup",
        r"contact",
    ],
    "user_and_account_management": [
        r"user_setting",
        r"user_identification",
        r"implicit_label",
        r"known_label",
        r"token",
        r"was\.user",
    ],
    "compliance_and_governance": [
        r"geo_location_set",
        r"label",
        r"quota",
        r"usage_invoice",
    ],
    # ===== I. Platform & Integrations (3 categories) =====
    "bigip_integration": [
        r"bigip",
        r"bigcne",
        r"irule",
        r"data_group",
    ],
    "nginx_one_management": [
        r"nginx",
    ],
    "platform_and_marketplace": [
        r"marketplace",
        r"pbac\.",
        r"addon_",
        r"tpm_",
        r"cminstance",
        r"voltshare",
        r"views\.third_party",
        r"views\.terraform",
        r"views\.external",
        r"views\.view_internal",
    ],
    # ===== J. Advanced & Emerging (3 categories) =====
    "advanced_ai_security": [
        r"ai_assistant",
        r"ai_data",
        r"flow_anomaly",
        r"malware_protection",
        r"shape\.recognize",
        r"shape\.safe",
        r"shape\.safeap",
        r"\.gia\.",
    ],
    "rate_limiting_and_quotas": [
        r"rate_limiter",
        r"policer",
    ],
    "configuration_and_deployment": [
        r"stored_object",
        r"manifest",
        r"certificate",
        r"config",
        r"trusted_ca",
        r"crl",
    ],
    # ===== K. UI & Platform Infrastructure (2 categories) =====
    "admin_console_and_ui": [
        r"ui_static",
        r"ui\.",
        r"navigation_tile",
    ],
    "billing_and_usage": [
        r"billing\.",
        r"usage",
        r"subscription",
        r"payment_method",
        r"plan_transition",
    ],
}


def backup_file(file_path: Path, backup_dir: Path) -> Path:
    """Create timestamped backup of file."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{file_path.stem}_{timestamp}.py"
    shutil.copy2(file_path, backup_path)
    return backup_path


def read_merge_specs(file_path: Path) -> str:
    """Read merge_specs.py file content."""
    with file_path.open() as f:
        return f.read()


def extract_domain_patterns(content: str) -> None:
    """Extract current DOMAIN_PATTERNS from file content (placeholder)."""
    # This is a simple extraction - assumes standard formatting
    match = re.search(r"DOMAIN_PATTERNS = \{(.*?)\n\}", content, re.DOTALL)
    if not match:
        raise ValueError("Could not find DOMAIN_PATTERNS in merge_specs.py")


def generate_new_patterns_code() -> str:
    """Generate Python code for new DOMAIN_PATTERNS dictionary."""
    lines = ["DOMAIN_PATTERNS = {"]

    for domain, patterns in NEW_DOMAIN_PATTERNS.items():
        lines.append(f'    "{domain}": [')
        lines.extend(f'        r"{pattern}",' for pattern in patterns)
        lines.append("    ],")

    lines.append("}")
    return "\n".join(lines)


def replace_domain_patterns(content: str, new_patterns_code: str) -> str:
    """Replace DOMAIN_PATTERNS dictionary in file content."""
    # Find and replace the DOMAIN_PATTERNS dictionary
    pattern = r"DOMAIN_PATTERNS = \{.*?\n\}"

    if not re.search(pattern, content, re.DOTALL):
        raise ValueError("Could not find DOMAIN_PATTERNS dictionary to replace")

    new_content = re.sub(pattern, new_patterns_code, content, flags=re.DOTALL)

    # Verify replacement worked
    if "DOMAIN_PATTERNS = {" not in new_content:
        raise ValueError("Failed to replace DOMAIN_PATTERNS")

    return new_content


def validate_patterns(patterns: dict[str, list[str]], spec_dir: Path) -> dict[str, Any]:
    """Validate patterns by checking categorization of all spec files."""
    spec_files = list(spec_dir.glob("*.json"))
    categorization: dict[str, list[str]] = defaultdict(list)
    uncategorized: list[str] = []

    for spec_file in spec_files:
        filename = spec_file.name.lower()
        found = False

        for domain, patterns_list in patterns.items():
            for pattern in patterns_list:
                if re.search(pattern, filename):
                    categorization[domain].append(spec_file.name)
                    found = True
                    break
            if found:
                break

        if not found:
            uncategorized.append(spec_file.name)

    return {
        "categorization": dict(categorization),
        "uncategorized": uncategorized,
        "total_specs": len(spec_files),
        "categorized": len(spec_files) - len(uncategorized),
        "domains_used": len(categorization),
    }


def main() -> int:
    """Main entry point for categorization update script."""
    parser = argparse.ArgumentParser(
        description="Idempotently update API endpoint categorization (23 → 31 domains)",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate categorization without modifying files",
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=Path(".backups"),
        help="Directory to store backups (default: .backups)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed categorization analysis",
    )

    args = parser.parse_args()

    # Paths
    project_root = Path(__file__).parent.parent
    merge_specs_path = project_root / "scripts" / "merge_specs.py"
    spec_dir = project_root / "specs" / "original"

    print("=" * 80)
    print("F5 XC API CATEGORIZATION UPDATE (Idempotent)")
    print("=" * 80)
    print()

    # Verify file exists
    if not merge_specs_path.exists():
        print(f"ERROR: {merge_specs_path} not found")
        return 1

    if not spec_dir.exists():
        print(f"ERROR: {spec_dir} not found")
        return 1

    print(f"Source file: {merge_specs_path}")
    print(f"Spec directory: {spec_dir}")
    print(f"New categories: {len(NEW_DOMAIN_PATTERNS)}")
    print(f"Backup directory: {args.backup_dir}")
    print()

    # Validate new patterns
    print("Validating new categorization patterns...")
    validation = validate_patterns(NEW_DOMAIN_PATTERNS, spec_dir)

    print(f"  Total spec files: {validation['total_specs']}")
    print(f"  Categorized: {validation['categorized']}")
    print(f"  Uncategorized (other): {len(validation['uncategorized'])}")
    print(f"  Categories used: {validation['domains_used']}/{len(NEW_DOMAIN_PATTERNS)}")
    print()

    if args.verbose:
        print("Categorization breakdown:")
        categorization_data = validation.get("categorization", {})
        for domain in sorted(categorization_data.keys()):
            count = len(categorization_data[domain])
            print(f"  {domain}: {count} specs")

        uncategorized_data = validation.get("uncategorized", [])
        if uncategorized_data:
            print(f"\n  {len(uncategorized_data)} specs without category:")
            for spec in sorted(uncategorized_data)[:10]:
                print(f"    - {spec}")
            if len(uncategorized_data) > 10:
                print(f"    ... and {len(uncategorized_data) - 10} more")
        print()

    # Check for empty domains
    empty_domains: list[str] = [
        d for d, specs in validation.get("categorization", {}).items() if not specs
    ]
    if empty_domains:
        print(f"WARNING: {len(empty_domains)} domains have no specs")
        if args.verbose:
            for domain in empty_domains:
                print(f"  - {domain}")
        print()

    # Check for high uncategorized rate
    if len(validation["uncategorized"]) > 10:
        print(f"WARNING: {len(validation['uncategorized'])} specs uncategorized")
        print("  Consider adding more patterns to handle these cases")
        print()

    if args.validate_only:
        print("✓ Validation complete (--validate-only, no changes made)")
        return 0

    # Read current file
    print("Reading current merge_specs.py...")
    current_content = read_merge_specs(merge_specs_path)

    # Create backup
    print("Creating backup...")
    backup_path = backup_file(merge_specs_path, args.backup_dir)
    print(f"  Backup: {backup_path}")
    print()

    # Generate and apply new patterns
    print("Generating new DOMAIN_PATTERNS...")
    new_patterns_code = generate_new_patterns_code()

    print("Replacing DOMAIN_PATTERNS in merge_specs.py...")
    try:
        new_content = replace_domain_patterns(current_content, new_patterns_code)
    except ValueError as e:
        print(f"ERROR: {e}")
        return 1

    # Write updated file
    print("Writing updated merge_specs.py...")
    with merge_specs_path.open("w") as f:
        f.write(new_content)

    print()
    print("=" * 80)
    print("✓ CATEGORIZATION UPDATE COMPLETE")
    print("=" * 80)
    print()
    print("Next steps:")
    print("  1. Review changes: git diff scripts/merge_specs.py")
    print("  2. Run pipeline: make pipeline")
    print("  3. Validate specs: make lint")
    print(
        "  4. Commit changes: git commit -am 'refactor: update API categorization (23→31 domains)'",
    )
    print()
    print(f"Backup saved to: {backup_path}")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
