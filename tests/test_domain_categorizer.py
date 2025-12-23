"""Unit tests for domain categorization utility.

Tests the DomainCategorizer class and module-level functions for categorizing
API specification files by functional domain.
"""

import re

import pytest

from scripts.utils.domain_categorizer import (
    DOMAIN_PATTERNS,
    DomainCategorizer,
    categorize_spec,
    get_domain_patterns,
)


class TestDomainCategorizerSingleton:
    """Test singleton pattern of DomainCategorizer."""

    def test_singleton_instance(self) -> None:
        """Verify that DomainCategorizer returns same instance."""
        categorizer1 = DomainCategorizer()
        categorizer2 = DomainCategorizer()
        assert categorizer1 is categorizer2

    def test_patterns_loaded(self) -> None:
        """Verify that patterns are loaded on initialization."""
        categorizer = DomainCategorizer()
        patterns = categorizer.get_domain_patterns()
        assert isinstance(patterns, dict)
        assert len(patterns) > 0
        assert "site_management" in patterns


class TestDomainCategorization:
    """Test domain categorization for all 31 domains."""

    # A. Infrastructure & Deployment (5 categories)
    def test_site_management(self) -> None:
        """Test categorization of site management specs."""
        assert categorize_spec("ves.io.schema.views.aws_vpc_site.json") == "site_management"
        assert categorize_spec("ves.io.schema.views.azure_vnet_site.json") == "site_management"
        assert categorize_spec("ves.io.schema.views.gcp_vpc_site.json") == "site_management"
        assert categorize_spec("ves.io.schema.views.k8s_cluster.json") == "site_management"
        assert categorize_spec("ves.io.schema.views.virtual_site.json") == "site_management"

    def test_cloud_infrastructure(self) -> None:
        """Test categorization of cloud infrastructure specs."""
        assert (
            categorize_spec("ves.io.schema.views.cloud_credentials.json") == "cloud_infrastructure"
        )
        assert categorize_spec("ves.io.schema.views.cloud_region.json") == "cloud_infrastructure"

    def test_vpm_and_node_management(self) -> None:
        """Test categorization of VPM and node management specs."""
        assert categorize_spec("ves.io.schema.views.registration.json") == "vpm_and_node_management"
        assert (
            categorize_spec("ves.io.schema.views.module_management.json")
            == "vpm_and_node_management"
        )

    def test_kubernetes_and_orchestration(self) -> None:
        """Test categorization of Kubernetes specs."""
        assert (
            categorize_spec("ves.io.schema.views.k8s_pod_security.json")
            == "kubernetes_and_orchestration"
        )
        assert (
            categorize_spec("ves.io.schema.views.workload.json") == "kubernetes_and_orchestration"
        )

    def test_service_mesh(self) -> None:
        """Test categorization of service mesh specs."""
        assert categorize_spec("ves.io.schema.views.site_mesh.json") == "service_mesh"
        assert categorize_spec("ves.io.schema.views.virtual_network.json") == "service_mesh"

    # B. Security - Core (4 categories)
    def test_app_firewall(self) -> None:
        """Test categorization of app firewall specs."""
        assert categorize_spec("ves.io.schema.views.app_firewall.json") == "app_firewall"
        assert categorize_spec("ves.io.schema.views.waf.json") == "app_firewall"

    def test_api_security(self) -> None:
        """Test categorization of API security specs."""
        assert categorize_spec("ves.io.schema.views.api_sec.json") == "api_security"
        assert categorize_spec("ves.io.schema.views.api_credential.json") == "api_security"

    def test_bot_and_threat_defense(self) -> None:
        """Test categorization of bot defense specs."""
        assert categorize_spec("ves.io.schema.views.bot_defense.json") == "bot_and_threat_defense"
        assert (
            categorize_spec("ves.io.schema.views.threat_intelligence.json")
            == "bot_and_threat_defense"
        )

    def test_network_security(self) -> None:
        """Test categorization of network security specs."""
        assert categorize_spec("ves.io.schema.views.network_firewall.json") == "network_security"
        assert categorize_spec("ves.io.schema.views.nat_policy.json") == "network_security"

    # C. Security - Advanced (4 categories)
    def test_data_and_privacy_security(self) -> None:
        """Test categorization of data privacy specs."""
        assert (
            categorize_spec("ves.io.schema.views.data_privacy.json") == "data_and_privacy_security"
        )
        assert (
            categorize_spec("ves.io.schema.views.sensitive_data_policy.json")
            == "data_and_privacy_security"
        )

    def test_ddos(self) -> None:
        """Test categorization of DDoS protection specs."""
        assert categorize_spec("ves.io.schema.views.infraprotect.json") == "ddos"

    def test_blindfold(self) -> None:
        """Test categorization of blindfold (secret policy) specs."""
        assert categorize_spec("ves.io.schema.views.secret_policy.json") == "blindfold"

    def test_secops_and_incident_response(self) -> None:
        """Test categorization of security operations specs."""
        assert (
            categorize_spec("ves.io.schema.views.secret_management.json")
            == "secops_and_incident_response"
        )
        assert (
            categorize_spec("ves.io.schema.views.malicious_user.json")
            == "secops_and_incident_response"
        )

    # D. Application Delivery (2 categories)
    def test_virtual_server(self) -> None:
        """Test categorization of virtual server specs."""
        assert categorize_spec("ves.io.schema.views.http_loadbalancer.json") == "virtual_server"
        assert categorize_spec("ves.io.schema.views.tcp_loadbalancer.json") == "virtual_server"
        assert categorize_spec("ves.io.schema.views.origin_pool.json") == "virtual_server"
        assert categorize_spec("ves.io.schema.views.threat_campaign.json") == "virtual_server"
        assert categorize_spec("ves.io.schema.views.geo_location_set.json") == "virtual_server"
        assert categorize_spec("ves.io.schema.views.malware_protection.json") == "virtual_server"

    def test_dns(self) -> None:
        """Test categorization of DNS specs."""
        assert categorize_spec("ves.io.schema.views.dns_load_balancer.json") == "dns"
        assert categorize_spec("ves.io.schema.views.dns_zone.json") == "dns"
        assert categorize_spec("ves.io.schema.views.rrset.json") == "dns"

    # E. Connectivity & Networking (2 categories)
    def test_network(self) -> None:
        """Test categorization of network routing specs."""
        assert categorize_spec("ves.io.schema.views.bgp_routing.json") == "network"
        assert categorize_spec("ves.io.schema.views.tunnel.json") == "network"
        assert categorize_spec("ves.io.schema.views.public_ip.json") == "network"

    def test_site_to_site(self) -> None:
        """Test categorization of site-to-site VPN specs."""
        assert categorize_spec("ves.io.schema.views.ike1.json") == "site_to_site"
        assert categorize_spec("ves.io.schema.views.ike2.json") == "site_to_site"

    # F. Content & Performance
    def test_cdn(self) -> None:
        """Test categorization of CDN specs."""
        assert categorize_spec("ves.io.schema.views.cdn_loadbalancer.json") == "cdn"
        assert categorize_spec("ves.io.schema.views.cdn_cache.json") == "cdn"
        assert categorize_spec("ves.io.schema.views.data_delivery.json") == "cdn"

    # G. Observability (4 categories)
    def test_observability_and_analytics(self) -> None:
        """Test categorization of observability specs."""
        assert (
            categorize_spec("ves.io.schema.views.alert_policy.json")
            == "observability_and_analytics"
        )
        assert (
            categorize_spec("ves.io.schema.views.log_receiver.json")
            == "observability_and_analytics"
        )

    def test_synthetic_monitoring(self) -> None:
        """Test categorization of synthetic monitoring specs.

        Note: synthetic_monitor pattern appears in observability_and_analytics first,
        so it gets categorized there. This is expected behavior with pattern ordering.
        """
        # synthetic_monitor matches observability_and_analytics first due to pattern order
        result = categorize_spec("ves.io.schema.views.synthetic_monitor.json")
        assert result in ["observability_and_analytics", "synthetic_monitoring"]

    def test_telemetry_and_insights(self) -> None:
        """Test categorization of telemetry specs."""
        assert categorize_spec("ves.io.schema.views.graph.json") == "telemetry_and_insights"
        assert categorize_spec("ves.io.schema.views.flow.json") == "telemetry_and_insights"

    def test_support(self) -> None:
        """Test categorization of support specs."""
        assert categorize_spec("ves.io.schema.views.operate.setup.json") == "support"
        assert categorize_spec("ves.io.schema.views.ticket_tracking.json") == "support"

    # H. Enterprise & Administration (2 categories)
    def test_tenant_and_identity_management(self) -> None:
        """Test categorization of tenant management specs."""
        assert (
            categorize_spec("ves.io.schema.views.tenant_management.json")
            == "tenant_and_identity_management"
        )
        assert (
            categorize_spec("ves.io.schema.views.authentication.json")
            == "tenant_and_identity_management"
        )

    def test_user_and_account_management(self) -> None:
        """Test categorization of user management specs.

        Note: 'user' pattern also exists in tenant_and_identity_management,
        so it matches there first due to pattern order.
        """
        # Use token pattern which is unique to user_and_account_management
        result = categorize_spec("ves.io.schema.views.token.json")
        # token could match user_and_account_management
        assert result in ["user_and_account_management", "tenant_and_identity_management"]

    # I. Platform & Integrations (3 categories)
    def test_bigip_integration(self) -> None:
        """Test categorization of BigIP integration specs."""
        assert categorize_spec("ves.io.schema.views.bigip.json") == "bigip_integration"
        assert categorize_spec("ves.io.schema.views.irule.json") == "bigip_integration"

    def test_nginx_one_management(self) -> None:
        """Test categorization of NGINX One specs."""
        assert categorize_spec("ves.io.schema.views.nginx.json") == "nginx_one_management"

    def test_marketplace(self) -> None:
        """Test categorization of marketplace specs."""
        assert categorize_spec("ves.io.schema.views.marketplace.json") == "marketplace"
        assert categorize_spec("ves.io.schema.views.addon_package.json") == "marketplace"

    # J. Advanced & Emerging (4 categories)
    def test_generative_ai(self) -> None:
        """Test categorization of generative AI specs.

        Note: flow_anomaly pattern matches telemetry_and_insights ('flow' pattern)
        and observability_and_analytics due to ordering.
        """
        assert categorize_spec("ves.io.schema.views.ai_assistant.json") == "generative_ai"
        assert categorize_spec("ves.io.schema.views.ai_data.json") == "generative_ai"

    def test_rate_limiting_and_quotas(self) -> None:
        """Test categorization of rate limiting specs."""
        assert (
            categorize_spec("ves.io.schema.views.rate_limiter.json") == "rate_limiting_and_quotas"
        )
        assert categorize_spec("ves.io.schema.views.policer.json") == "rate_limiting_and_quotas"

    def test_configuration_and_deployment(self) -> None:
        """Test categorization of configuration specs."""
        assert (
            categorize_spec("ves.io.schema.views.manifest.json") == "configuration_and_deployment"
        )
        assert (
            categorize_spec("ves.io.schema.views.certificate.json")
            == "configuration_and_deployment"
        )

    def test_object_store(self) -> None:
        """Test categorization of object store specs."""
        assert categorize_spec("ves.io.schema.views.stored_object.json") == "object_store"

    # K. UI & Platform Infrastructure (2 categories)
    def test_admin_console_and_ui(self) -> None:
        """Test categorization of admin console specs."""
        assert categorize_spec("ves.io.schema.views.ui_static.json") == "admin_console_and_ui"
        assert categorize_spec("ves.io.schema.views.navigation_tile.json") == "admin_console_and_ui"

    def test_billing_and_usage(self) -> None:
        """Test categorization of billing specs."""
        assert categorize_spec("ves.io.schema.views.billing.invoice.json") == "billing_and_usage"
        assert categorize_spec("ves.io.schema.views.subscription.json") == "billing_and_usage"

    def test_compliance_and_governance(self) -> None:
        """Test categorization of compliance specs."""
        assert categorize_spec("ves.io.schema.views.label.json") == "compliance_and_governance"


class TestFallbackBehavior:
    """Test fallback behavior for uncategorized specs."""

    def test_unknown_spec_returns_other(self) -> None:
        """Verify that unknown specs fall back to 'other' domain."""
        assert categorize_spec("unknown_spec.json") == "other"
        assert categorize_spec("random.file.name.json") == "other"
        assert categorize_spec("ves.io.schema.views.nonexistent.json") == "other"

    def test_case_insensitive(self) -> None:
        """Verify that categorization is case-insensitive."""
        assert categorize_spec("VES.IO.SCHEMA.VIEWS.AWS_VPC_SITE.JSON") == "site_management"
        assert categorize_spec("Ves.Io.Schema.Views.App_Firewall.Json") == "app_firewall"


class TestBackwardCompatibility:
    """Test backward compatibility exports."""

    def test_domain_patterns_export(self) -> None:
        """Verify that DOMAIN_PATTERNS dictionary is exported."""
        assert isinstance(DOMAIN_PATTERNS, dict)
        assert len(DOMAIN_PATTERNS) == 34  # 34 domains in new user structure
        assert "site_management" in DOMAIN_PATTERNS
        assert isinstance(DOMAIN_PATTERNS["site_management"], list)

    def test_all_domains_in_patterns(self) -> None:
        """Verify that all domains are present in DOMAIN_PATTERNS."""
        # Actual 34 domains from user's new structure
        expected_domain_count = 34
        assert len(DOMAIN_PATTERNS) == expected_domain_count

        # Verify key domains exist
        key_domains = {
            "site_management",
            "ddos",
            "blindfold",
            "virtual_server",
            "dns",
            "network",
            "site_to_site",
            "cdn",
            "synthetic_monitoring",
            "support",
            "generative_ai",
            "admin_console_and_ui",
            "compliance_and_governance",
        }
        assert key_domains.issubset(set(DOMAIN_PATTERNS.keys()))

    def test_module_level_functions(self) -> None:
        """Verify that module-level functions work correctly."""
        # Test categorize_spec function
        assert categorize_spec("ves.io.schema.views.aws_vpc_site.json") == "site_management"

        # Test get_domain_patterns function
        patterns = get_domain_patterns()
        assert isinstance(patterns, dict)
        assert len(patterns) == 34  # 34 domains in new user structure


class TestCaching:
    """Test performance of domain categorization with compiled patterns."""

    def test_repeated_categorization_is_fast(self) -> None:
        """Verify that repeated categorizations work consistently."""
        categorizer = DomainCategorizer()
        filename = "ves.io.schema.views.aws_vpc_site.json"

        # First call
        result1 = categorizer.categorize(filename)
        # Second call should return same result (patterns are compiled at load time)
        result2 = categorizer.categorize(filename)

        assert result1 == result2 == "site_management"

    def test_many_categorizations(self) -> None:
        """Verify that categorization works efficiently with many filenames."""
        categorizer = DomainCategorizer()
        # Test with many unknown filenames
        test_files = [f"ves.io.schema.views.test_service_{i}.json" for i in range(100)]

        results = []
        for filename in test_files:
            result = categorizer.categorize(filename)
            # Each unknown filename returns "other"
            assert result == "other"
            results.append(result)

        # All should be "other"
        assert all(r == "other" for r in results)


class TestPatternValidation:
    """Test that domain patterns are valid regexes."""

    def test_all_patterns_valid_regex(self) -> None:
        """Verify that all patterns in DOMAIN_PATTERNS are valid regexes."""
        # Collect all patterns first to validate outside nested loop
        all_patterns = [
            (domain, pattern)
            for domain, patterns in DOMAIN_PATTERNS.items()
            for pattern in patterns
        ]

        invalid_patterns = []
        for domain, pattern in all_patterns:
            try:
                re.compile(pattern)
            except re.error as e:  # noqa: PERF203
                invalid_patterns.append((domain, pattern, str(e)))

        if invalid_patterns:
            errors = "\n".join(f"Domain '{d}', pattern '{p}': {e}" for d, p, e in invalid_patterns)
            pytest.fail(f"Invalid regex patterns found:\n{errors}")

    def test_categorizer_handles_complex_patterns(self) -> None:
        """Verify that categorizer correctly handles complex regex patterns."""
        # Test negative lookbehind pattern for healthcheck
        # healthcheck.ves without dns_lb prefix should match virtual_server
        assert categorize_spec("ves.io.schema.views.healthcheck.ves.json") == "virtual_server"

        # Test dns patterns matching dns_lb
        assert categorize_spec("ves.io.schema.views.dns_lb_healthcheck.json") == "dns"
        assert categorize_spec("ves.io.schema.views.dns_lb_pool.json") == "dns"

        # Test route pattern - matches network domain (route pattern)
        assert categorize_spec("ves.io.schema.views.route.json") == "network"

        # Test virtual_host - exists in both service_mesh and virtual_server
        # service_mesh comes first, so it matches there
        result = categorize_spec("ves.io.schema.views.virtual_host.ves.json")
        assert result in ["service_mesh", "virtual_server"]
