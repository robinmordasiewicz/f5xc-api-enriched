"""Tests for MinimumConfigurationEnricher.

Tests the enrichment of OpenAPI specs with minimum configuration metadata
for AI-assisted resource creation.
"""

import pytest

from scripts.utils.minimum_configuration_enricher import (
    MinimumConfigurationEnricher,
    MinimumConfigurationStats,
)


class TestMinimumConfigurationStats:
    """Test MinimumConfigurationStats dataclass."""

    def test_stats_initialization(self):
        """Test stats initialization with default values."""
        stats = MinimumConfigurationStats()
        assert stats.schemas_enriched == 0
        assert stats.minimum_configs_added == 0
        assert stats.required_fields_added == 0
        assert stats.field_requirements_added == 0
        assert stats.example_yamls_generated == 0
        assert stats.example_jsons_generated == 0
        assert stats.example_curls_generated == 0
        assert stats.cli_domains_added == 0
        assert stats.cli_aliases_added == 0
        assert stats.errors == []

    def test_stats_to_dict(self):
        """Test stats conversion to dictionary."""
        stats = MinimumConfigurationStats()
        stats.schemas_enriched = 5
        stats.minimum_configs_added = 5
        stats.required_fields_added = 10

        result = stats.to_dict()
        assert result["schemas_enriched"] == 5
        assert result["minimum_configs_added"] == 5
        assert result["required_fields_added"] == 10
        assert "error_count" in result


class TestMinimumConfigurationEnricherBasics:
    """Test basic MinimumConfigurationEnricher functionality."""

    def test_enricher_initialization(self):
        """Test enricher initializes with config loaded."""
        enricher = MinimumConfigurationEnricher()
        assert enricher.config is not None
        assert enricher.resources is not None
        assert len(enricher.resources) > 0
        assert enricher.stats is not None

    def test_resources_loaded(self):
        """Test that all 5 priority resources are loaded."""
        enricher = MinimumConfigurationEnricher()
        expected_resources = {
            "http_loadbalancer",
            "origin_pool",
            "tcp_loadbalancer",
            "healthcheck",
            "app_firewall",
        }
        loaded_resources = set(enricher.resources.keys())
        for resource in expected_resources:
            assert resource in loaded_resources, f"Missing resource: {resource}"

    def test_domain_categorizer_initialized(self):
        """Test that DomainCategorizer singleton is initialized."""
        enricher = MinimumConfigurationEnricher()
        assert enricher.domain_categorizer is not None
        # Verify it can categorize schemas
        domain = enricher.domain_categorizer.categorize("http_loadbalancer")
        assert domain is not None


class TestResourceDetection:
    """Test resource type detection from schema names."""

    def test_detect_direct_match(self):
        """Test direct schema name match."""
        enricher = MinimumConfigurationEnricher()
        assert enricher._detect_resource_type("http_loadbalancer") == "http_loadbalancer"  # noqa: SLF001
        assert enricher._detect_resource_type("origin_pool") == "origin_pool"  # noqa: SLF001

    def test_detect_with_request_suffix(self):
        """Test detection with Request suffix."""
        enricher = MinimumConfigurationEnricher()
        assert (
            enricher._detect_resource_type("http_loadbalancerCreateRequest") == "http_loadbalancer"  # noqa: SLF001
        )
        assert enricher._detect_resource_type("origin_poolCreateRequest") == "origin_pool"  # noqa: SLF001

    def test_detect_with_spec_type_suffix(self):
        """Test detection with SpecType suffix."""
        enricher = MinimumConfigurationEnricher()
        assert (
            enricher._detect_resource_type("http_loadbalancerCreateSpecType") == "http_loadbalancer"  # noqa: SLF001
        )
        assert enricher._detect_resource_type("healthcheckCreateSpecType") == "healthcheck"  # noqa: SLF001

    def test_detect_with_response_suffix(self):
        """Test detection with Response suffix."""
        enricher = MinimumConfigurationEnricher()
        assert enricher._detect_resource_type("origin_poolCreateResponse") == "origin_pool"  # noqa: SLF001
        assert enricher._detect_resource_type("tcp_loadbalancerGetResponse") == "tcp_loadbalancer"  # noqa: SLF001

    def test_detect_partial_matching(self):
        """Test partial matching for compound names."""
        enricher = MinimumConfigurationEnricher()
        # Should find 'app_firewall' in longer name
        result = enricher._detect_resource_type("app_firewallSomeOtherType")  # noqa: SLF001
        assert result == "app_firewall"

    def test_detect_no_match(self):
        """Test detection with non-matching schema."""
        enricher = MinimumConfigurationEnricher()
        result = enricher._detect_resource_type("SomeRandomSchema")  # noqa: SLF001
        assert result is None

    def test_detect_http_loadbalancer_variants(self):
        """Test detection of various http_loadbalancer schema name variations."""
        enricher = MinimumConfigurationEnricher()
        variants = [
            "http_loadbalancerCreateRequest",
            "http_loadbalancerUpdateRequest",
            "http_loadbalancerGetResponse",
            "http_loadbalancerDeleteResponse",
            "http_loadbalancerCreateSpecType",
            "http_loadbalancerUpdateSpecType",
            "http_loadbalancerGetSpecType",
        ]
        for variant in variants:
            result = enricher._detect_resource_type(variant)  # noqa: SLF001
            assert result == "http_loadbalancer", f"Failed to detect {variant}"


class TestRequiredFieldExtraction:
    """Test extraction of required fields from schema."""

    def test_extract_config_required_fields(self):
        """Test extraction of required fields from config."""
        enricher = MinimumConfigurationEnricher()
        resource_type = "http_loadbalancer"
        schema = {}

        required = enricher._extract_required_fields(resource_type, schema)  # noqa: SLF001
        assert isinstance(required, list)
        assert len(required) > 0
        # Should include metadata.name and metadata.namespace
        assert any("metadata.name" in field for field in required)

    def test_extract_required_fields_from_nested_config(self):
        """Test extraction handles nested field paths."""
        enricher = MinimumConfigurationEnricher()
        required_fields = enricher.resources.get("origin_pool", {}).get("required_fields", [])
        assert required_fields is not None
        assert len(required_fields) > 0


class TestExampleGeneration:
    """Test example YAML and CLI command generation."""

    def test_example_yaml_generation(self):
        """Test that example YAML is configured for resources."""
        enricher = MinimumConfigurationEnricher()
        for resource in [
            "http_loadbalancer",
            "origin_pool",
            "tcp_loadbalancer",
            "healthcheck",
            "app_firewall",
        ]:
            resource_config = enricher.resources.get(resource, {})
            example_yaml = resource_config.get("example_yaml", "")
            assert example_yaml, f"No example_yaml for {resource}"
            assert "apiVersion" in example_yaml or "kind" in example_yaml, (
                f"Invalid YAML structure for {resource}"
            )

    def test_example_curl_generation(self):
        """Test that example curl commands are configured for resources."""
        enricher = MinimumConfigurationEnricher()
        for resource in [
            "http_loadbalancer",
            "origin_pool",
            "tcp_loadbalancer",
            "healthcheck",
            "app_firewall",
        ]:
            resource_config = enricher.resources.get(resource, {})
            example_curl = resource_config.get("example_curl", "")
            assert example_curl, f"No example_curl for {resource}"
            assert "curl" in example_curl, f"Invalid curl command for {resource}"
            assert "F5XC_API_URL" in example_curl, f"Missing API URL var for {resource}"
            assert "F5XC_API_TOKEN" in example_curl, f"Missing token var for {resource}"

    def test_example_json_configured(self):
        """Test that example JSON is configured for resources."""
        enricher = MinimumConfigurationEnricher()
        for resource in [
            "http_loadbalancer",
            "origin_pool",
            "tcp_loadbalancer",
            "healthcheck",
            "app_firewall",
        ]:
            resource_config = enricher.resources.get(resource, {})
            example_json = resource_config.get("example_json", "")
            assert example_json, f"No example_json for {resource}"
            assert "metadata" in example_json, f"Invalid JSON structure for {resource}"

    def test_cli_aliases_configured(self):
        """Test that CLI aliases are explicitly configured."""
        enricher = MinimumConfigurationEnricher()
        for resource in [
            "http_loadbalancer",
            "origin_pool",
            "tcp_loadbalancer",
            "healthcheck",
            "app_firewall",
        ]:
            resource_config = enricher.resources.get(resource, {})
            cli_config = resource_config.get("cli", {})
            aliases = cli_config.get("aliases", [])
            assert isinstance(aliases, list), f"CLI aliases not configured for {resource}"


class TestDomainMapping:
    """Test domain classification for resources."""

    def test_get_domain_for_http_loadbalancer(self):
        """Test domain mapping for http_loadbalancer."""
        enricher = MinimumConfigurationEnricher()
        domain = enricher._get_domain_for_resource(  # noqa: SLF001
            "http_loadbalancer",
            "http_loadbalancerCreateRequest",
        )
        assert domain is not None
        assert domain in ["virtual", "cdn", "loadbalancing"]

    def test_get_domain_for_app_firewall(self):
        """Test domain mapping for app_firewall."""
        enricher = MinimumConfigurationEnricher()
        domain = enricher._get_domain_for_resource("app_firewall", "app_firewallCreateRequest")  # noqa: SLF001
        assert domain == "waf"

    def test_get_domain_explicit_config(self):
        """Test that explicit domain in config is used."""
        enricher = MinimumConfigurationEnricher()
        # http_loadbalancer should have explicit domain configured
        domain = enricher._get_domain_for_resource(  # noqa: SLF001
            "http_loadbalancer",
            "http_loadbalancerCreateRequest",
        )
        assert domain is not None


class TestFullEnrichment:
    """Test full enrichment workflow."""

    def test_enrich_spec_with_resources(self):
        """Test enriching spec with resource schemas."""
        enricher = MinimumConfigurationEnricher()

        # Create minimal spec with http_loadbalancer schema
        spec = {
            "components": {
                "schemas": {
                    "http_loadbalancerCreateRequest": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "namespace": {"type": "string"},
                        },
                    },
                },
            },
        }

        enriched = enricher.enrich_spec(spec)

        # Verify schema was enriched with minimum configuration
        schema = enriched["components"]["schemas"]["http_loadbalancerCreateRequest"]
        assert "x-ves-minimum-configuration" in schema
        assert "x-ves-cli-domain" in schema
        assert enricher.stats.minimum_configs_added > 0

    def test_enrich_preserves_original_schema(self):
        """Test that enrichment preserves original schema properties."""
        enricher = MinimumConfigurationEnricher()

        original_type = "object"
        original_properties = {"name": {"type": "string"}}

        spec = {
            "components": {
                "schemas": {
                    "http_loadbalancerCreateRequest": {
                        "type": original_type,
                        "properties": original_properties,
                    },
                },
            },
        }

        enriched = enricher.enrich_spec(spec)
        schema = enriched["components"]["schemas"]["http_loadbalancerCreateRequest"]

        # Verify original properties are preserved
        assert schema["type"] == original_type
        assert schema["properties"] == original_properties

    def test_enrich_empty_spec(self):
        """Test enriching spec with no schemas."""
        enricher = MinimumConfigurationEnricher()
        spec = {"components": {"schemas": {}}}
        enricher.enrich_spec(spec)
        assert enricher.stats.minimum_configs_added == 0

    def test_enrich_no_matching_resources(self):
        """Test enriching spec with no matching resources."""
        enricher = MinimumConfigurationEnricher()
        spec = {
            "components": {
                "schemas": {
                    "UnrelatedSchema": {"type": "object"},
                },
            },
        }
        enricher.enrich_spec(spec)
        assert enricher.stats.minimum_configs_added == 0

    def test_stats_collection(self):
        """Test that statistics are properly collected during enrichment."""
        enricher = MinimumConfigurationEnricher()

        spec = {
            "components": {
                "schemas": {
                    "http_loadbalancerCreateRequest": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                    },
                    "origin_poolCreateRequest": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                    },
                },
            },
        }

        enricher.enrich_spec(spec)
        stats = enricher.get_stats()

        assert stats["schemas_enriched"] >= 2
        assert stats["minimum_configs_added"] >= 2
        assert stats["cli_domains_added"] >= 2
        assert len(stats["errors"]) == 0


class TestAllFiveResources:
    """Test enrichment for all 5 priority resources."""

    @pytest.mark.parametrize(
        ("resource_type", "schema_name"),
        [
            ("http_loadbalancer", "http_loadbalancerCreateRequest"),
            ("origin_pool", "origin_poolCreateRequest"),
            ("tcp_loadbalancer", "tcp_loadbalancerCreateRequest"),
            ("healthcheck", "healthcheckCreateRequest"),
            ("app_firewall", "app_firewallCreateRequest"),
        ],
    )
    def test_enrich_all_resources(self, resource_type, schema_name):
        """Test enrichment for all 5 resources."""
        enricher = MinimumConfigurationEnricher()

        spec = {
            "components": {
                "schemas": {
                    schema_name: {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                    },
                },
            },
        }

        enriched = enricher.enrich_spec(spec)
        schema = enriched["components"]["schemas"][schema_name]

        # Verify minimum configuration was added
        assert "x-ves-minimum-configuration" in schema, f"No minimum config for {resource_type}"

        min_config = schema["x-ves-minimum-configuration"]
        assert "required_fields" in min_config
        assert "description" in min_config
        assert "example_yaml" in min_config
        assert "example_json" in min_config
        assert "example_curl" in min_config

        # Verify CLI metadata was added
        assert "x-ves-cli-domain" in schema
        assert schema["x-ves-cli-domain"] is not None


class TestAutoGenerationForUnconfiguredResources:
    """Test auto-generation for resources without explicit configuration."""

    def test_auto_generate_unconfigured_schema(self):
        """Test auto-generation for a schema without explicit configuration."""
        enricher = MinimumConfigurationEnricher()

        # Create a spec with an unconfigured schema
        spec = {
            "components": {
                "schemas": {
                    "RandomUnknownSchema": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "description": {"type": "string"},
                            "status": {"type": "string"},
                        },
                    },
                },
            },
        }

        enriched = enricher.enrich_spec(spec)
        schema = enriched["components"]["schemas"]["RandomUnknownSchema"]

        # Verify auto-generated minimum configuration was added
        assert "x-ves-minimum-configuration" in schema
        min_config = schema["x-ves-minimum-configuration"]
        assert "description" in min_config
        assert "Minimum configuration for" in min_config["description"]
        assert min_config["required_fields"] is not None
        assert min_config["example_yaml"] is not None

        # Verify auto-generated CLI domain
        assert "x-ves-cli-domain" in schema
        # Should have been auto-categorized or fallback
        assert schema["x-ves-cli-domain"] is not None

    def test_auto_generation_stats_tracked(self):
        """Test that auto-generation statistics are properly tracked."""
        enricher = MinimumConfigurationEnricher()

        spec = {
            "components": {
                "schemas": {
                    "UnknownResource1": {"type": "object"},
                    "UnknownResource2": {"type": "object"},
                    "http_loadbalancerCreateRequest": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                    },
                },
            },
        }

        enricher.enrich_spec(spec)
        stats = enricher.get_stats()

        # Should have auto-generated 2 resources
        assert stats["schemas_auto_generated"] >= 2
        # Configured resource should be counted separately
        assert stats["minimum_configs_added"] >= 1

    def test_multiple_unconfigured_resources(self):
        """Test auto-generation for multiple unconfigured resources."""
        enricher = MinimumConfigurationEnricher()

        # Create specs with various unconfigured resource patterns
        spec = {
            "components": {
                "schemas": {
                    "customTypeA": {"type": "object", "properties": {}},
                    "customTypeB": {"type": "string"},
                    "customTypeC": {"type": "object", "properties": {"id": {"type": "string"}}},
                    "customTypeD": {"type": "array"},
                },
            },
        }

        enriched = enricher.enrich_spec(spec)
        schemas = enriched["components"]["schemas"]

        # All should have been enriched
        for schema_name in ["customTypeA", "customTypeB", "customTypeC", "customTypeD"]:
            schema = schemas[schema_name]
            assert "x-ves-cli-domain" in schema
            assert schema["x-ves-cli-domain"] is not None


class TestIdempotency:
    """Test idempotent behavior - running enrichment multiple times produces consistent results."""

    def test_preserve_existing_cli_domain(self):
        """Test that existing x-ves-cli-domain is preserved (idempotent)."""
        enricher = MinimumConfigurationEnricher()

        # Create a spec with manually-set x-ves-cli-domain
        spec = {
            "components": {
                "schemas": {
                    "custom_resource": {
                        "type": "object",
                        "x-ves-cli-domain": "my_custom_domain",
                    },
                },
            },
        }

        enriched = enricher.enrich_spec(spec)
        schema = enriched["components"]["schemas"]["custom_resource"]

        # Should preserve the existing value
        assert schema["x-ves-cli-domain"] == "my_custom_domain"
        # Should have recorded that it was preserved
        assert enricher.stats.cli_domains_preserved > 0

    def test_multiple_enrichment_passes_idempotent(self):
        """Test that running enrichment twice produces identical results."""
        spec_original = {
            "components": {
                "schemas": {
                    "http_loadbalancerCreateRequest": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                    },
                },
            },
        }

        # First pass
        enricher1 = MinimumConfigurationEnricher()
        result1 = enricher1.enrich_spec(spec_original.copy())

        # Second pass - use the enriched result as input
        enricher2 = MinimumConfigurationEnricher()
        result2 = enricher2.enrich_spec(result1)

        # Results should be identical
        schema1 = result1["components"]["schemas"]["http_loadbalancerCreateRequest"]
        schema2 = result2["components"]["schemas"]["http_loadbalancerCreateRequest"]

        assert schema1.get("x-ves-cli-domain") == schema2.get("x-ves-cli-domain")
        assert schema1.get("x-ves-minimum-configuration") == schema2.get(
            "x-ves-minimum-configuration",
        )

    def test_idempotent_stats_tracking(self):
        """Test that idempotent behavior is properly tracked in stats."""
        enricher = MinimumConfigurationEnricher()

        spec = {
            "components": {
                "schemas": {
                    "http_loadbalancerCreateRequest": {
                        "type": "object",
                        "properties": {},
                    },
                    "origin_poolCreateRequest": {"type": "object", "properties": {}},
                },
            },
        }

        enricher.enrich_spec(spec)
        stats = enricher.get_stats()

        # Both resources should have been enriched
        assert stats["schemas_enriched"] >= 2
        # At least some CLI domains should have been added
        assert stats["cli_domains_added"] >= 2
        # No domains should have been preserved initially
        assert stats["cli_domains_preserved"] == 0


class TestAllResourcePatterns:
    """Test enrichment across various resource naming patterns."""

    @pytest.mark.parametrize(
        "schema_name",
        [
            "http_loadbalancerCreateRequest",
            "origin_poolGetResponse",
            "tcp_loadbalancerUpdateRequest",
            "healthcheckDeleteResponse",
            "app_firewallCreateSpecType",
            "unknownResourceType",
            "anotherRandomResource",
        ],
    )
    def test_enrich_various_resource_patterns(self, schema_name):
        """Test enrichment for various resource naming patterns."""
        enricher = MinimumConfigurationEnricher()

        spec = {
            "components": {
                "schemas": {
                    schema_name: {
                        "type": "object",
                        "properties": {"id": {"type": "string"}},
                    },
                },
            },
        }

        enriched = enricher.enrich_spec(spec)
        schema = enriched["components"]["schemas"][schema_name]

        # All schemas should be enriched with minimum configuration
        assert "x-ves-minimum-configuration" in schema
        min_config = schema["x-ves-minimum-configuration"]
        assert min_config.get("description") is not None
        assert min_config.get("example_yaml") is not None
        assert min_config.get("required_fields") is not None

        # All should have CLI domain
        assert "x-ves-cli-domain" in schema
        assert schema["x-ves-cli-domain"] is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
