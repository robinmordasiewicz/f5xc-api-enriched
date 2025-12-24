"""Unit tests for ValidationEnricher."""

from pathlib import Path

import pytest

from scripts.utils.validation_enricher import ValidationEnricher


@pytest.fixture
def enricher():
    """Create enricher with default config."""
    return ValidationEnricher()


@pytest.fixture
def simple_spec():
    """Create a simple OpenAPI spec for testing."""
    return {
        "components": {
            "schemas": {
                "User": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "email": {"type": "string"},
                        "port": {"type": "integer"},
                        "id": {"type": "string"},
                    },
                },
            },
        },
    }


class TestValidationEnricherBasics:
    """Test basic enricher functionality."""

    def test_initialization(self):
        """Test enricher initializes with default config."""
        enricher = ValidationEnricher()
        assert enricher.merge_discovery_constraints is True
        assert len(enricher.validation_patterns) > 0
        assert len(enricher.type_defaults) > 0

    def test_config_loading_missing_file(self):
        """Test enricher loads defaults when config file missing."""
        enricher = ValidationEnricher(config_path=Path("/nonexistent/path.yaml"))
        assert enricher.merge_discovery_constraints is True
        assert len(enricher.validation_patterns) > 0
        assert "string" in enricher.type_defaults

    def test_stats_initialization(self):
        """Test enrichment stats start at zero."""
        enricher = ValidationEnricher()
        stats = enricher.get_stats()
        assert stats["patterns_added"] == 0
        assert stats["constraints_added"] == 0
        assert stats["properties_processed"] == 0
        assert stats["schemas_processed"] == 0


class TestTypeDefaults:
    """Test type-level default constraints."""

    def test_string_type_gets_defaults(self, enricher):
        """Test that string type gets default min/maxLength."""
        prop = {"type": "string"}
        enricher._apply_type_defaults(prop)

        assert "minLength" in prop
        assert "maxLength" in prop
        assert prop["minLength"] == 0
        assert prop["maxLength"] == 1024

    def test_integer_type_gets_defaults(self, enricher):
        """Test that integer type gets default min/max."""
        prop = {"type": "integer"}
        enricher._apply_type_defaults(prop)

        assert "minimum" in prop
        assert "maximum" in prop
        assert prop["minimum"] == 0
        assert prop["maximum"] == 2147483647

    def test_existing_defaults_preserved(self, enricher):
        """Test that existing defaults are not overwritten."""
        prop = {"type": "string", "minLength": 5, "maxLength": 100}
        enricher._apply_type_defaults(prop)

        # Should preserve existing values
        assert prop["minLength"] == 5
        assert prop["maxLength"] == 100

    def test_non_standard_type_skipped(self, enricher):
        """Test that types without defaults are skipped."""
        prop = {"type": "boolean"}
        enricher._apply_type_defaults(prop)

        # Boolean has no defaults, should not be added
        assert "minimum" not in prop
        assert "minLength" not in prop


class TestPatternValidation:
    """Test pattern-based validation rules."""

    def test_email_gets_format(self, enricher):
        """Test that email field gets format and pattern."""
        prop = {"type": "string"}
        enricher._apply_pattern_rules(prop, "email")

        assert "format" in prop
        assert prop["format"] == "email"
        assert "pattern" in prop

    def test_port_gets_range(self, enricher):
        """Test that port field gets min/max constraints."""
        prop = {"type": "integer"}
        enricher._apply_pattern_rules(prop, "port")

        assert "minimum" in prop
        assert "maximum" in prop
        assert prop["minimum"] == 1
        assert prop["maximum"] == 65535

    def test_vlan_id_gets_range(self, enricher):
        """Test that VLAN ID field gets valid range."""
        prop = {"type": "integer"}
        enricher._apply_pattern_rules(prop, "vlan_id")

        assert "minimum" in prop
        assert "maximum" in prop
        assert prop["minimum"] == 1
        assert prop["maximum"] == 4094

    def test_uuid_gets_format(self, enricher):
        """Test that UUID field gets format."""
        prop = {"type": "string"}
        enricher._apply_pattern_rules(prop, "uuid")

        assert "format" in prop
        assert prop["format"] == "uuid"

    def test_url_gets_format(self, enricher):
        """Test that URL field gets URI format."""
        prop = {"type": "string"}
        enricher._apply_pattern_rules(prop, "url")

        assert "format" in prop
        assert prop["format"] == "uri"

    def test_timestamp_gets_format(self, enricher):
        """Test that timestamp field gets date-time format."""
        prop = {"type": "string"}
        enricher._apply_pattern_rules(prop, "timestamp")

        assert "format" in prop
        assert prop["format"] == "date-time"

    def test_ipv4_gets_format(self, enricher):
        """Test that IPv4 field gets ipv4 format."""
        prop = {"type": "string"}
        enricher._apply_pattern_rules(prop, "ipv4")

        assert "format" in prop
        assert prop["format"] == "ipv4"

    def test_existing_constraints_preserved(self, enricher):
        """Test that existing pattern constraints are not overwritten."""
        prop = {
            "type": "integer",
            "minimum": 10,
            "maximum": 100,
        }
        enricher._apply_pattern_rules(prop, "port")

        # Should preserve existing values
        assert prop["minimum"] == 10
        assert prop["maximum"] == 100

    def test_generic_field_no_rules(self, enricher):
        """Test that generic field names don't get pattern rules."""
        prop = {"type": "string"}
        original = prop.copy()
        enricher._apply_pattern_rules(prop, "value")

        # No pattern should match "value"
        assert prop == original


class TestPropertyEnrichment:
    """Test property-level enrichment."""

    def test_property_enrichment_combines_constraints(self, enricher):
        """Test that property enrichment combines type and pattern constraints."""
        prop = {"type": "integer"}
        enricher._enrich_property(prop, "port")

        # Should have constraints from both type defaults and pattern rules
        assert "minimum" in prop
        assert "maximum" in prop

    def test_email_field_comprehensive_enrichment(self, enricher):
        """Test comprehensive enrichment of email field."""
        prop = {"type": "string"}
        enricher._enrich_property(prop, "email")

        # Should have format, pattern, and type defaults
        assert "format" in prop
        assert "pattern" in prop
        assert "minLength" in prop  # From string type defaults
        assert "maxLength" in prop

    def test_stats_tracked_on_enrichment(self, enricher):
        """Test that stats are updated during enrichment."""
        prop = {"type": "string"}
        enricher._enrich_property(prop, "email")

        stats = enricher.get_stats()
        assert stats["patterns_added"] > 0
        assert stats["constraints_added"] > 0


class TestSpecEnrichment:
    """Test full specification enrichment."""

    def test_enrich_simple_spec(self, enricher, simple_spec):
        """Test enriching a simple OpenAPI spec."""
        result = enricher.enrich_spec(simple_spec)

        # Check that spec structure is preserved
        assert "components" in result
        assert "schemas" in result["components"]
        assert "User" in result["components"]["schemas"]

        # Check that port field was enriched with range
        user_props = result["components"]["schemas"]["User"]["properties"]
        port_prop = user_props["port"]
        assert port_prop["minimum"] == 1
        assert port_prop["maximum"] == 65535

        # Check that string fields got type defaults
        email_prop = user_props["email"]
        assert "minLength" in email_prop
        assert "maxLength" in email_prop

    def test_stats_updated_on_full_enrichment(self, enricher, simple_spec):
        """Test that stats are updated on full spec enrichment."""
        enricher.enrich_spec(simple_spec)
        stats = enricher.get_stats()

        assert stats["schemas_processed"] > 0
        assert stats["properties_processed"] > 0
        assert stats["constraints_added"] > 0

    def test_nested_schemas_processed(self, enricher):
        """Test that nested schemas are processed."""
        spec = {
            "components": {
                "schemas": {
                    "Address": {
                        "type": "object",
                        "properties": {
                            "port": {"type": "integer"},
                            "email": {"type": "string"},
                        },
                    },
                    "Person": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "address": {"$ref": "#/components/schemas/Address"},
                        },
                    },
                },
            },
        }

        result = enricher.enrich_spec(spec)
        stats = enricher.get_stats()

        # Both schemas should be processed
        assert stats["schemas_processed"] >= 2

        # Port field should get validation
        port_prop = result["components"]["schemas"]["Address"]["properties"]["port"]
        assert "minimum" in port_prop
        assert "maximum" in port_prop


class TestDiscoveryConstraintMerging:
    """Test merging with discovery constraints."""

    def test_discovery_constraints_merged(self, enricher):
        """Test that discovery constraints are merged."""
        prop = {
            "type": "string",
            "x-ves-validation-rules": {
                "pattern": "^[A-Z]+$",
                "maxLength": 50,
            },
        }

        enricher._merge_discovery_constraints(prop, "test")

        # Discovery constraints should be present
        assert prop["pattern"] == "^[A-Z]+$"
        assert prop["maxLength"] == 50

    def test_existing_constraints_take_priority(self, enricher):
        """Test that existing constraints override discovery."""
        prop = {
            "type": "string",
            "minLength": 10,
            "x-ves-validation-rules": {
                "minLength": 5,
            },
        }

        enricher._merge_discovery_constraints(prop, "test")

        # Existing constraint should be preserved
        assert prop["minLength"] == 10


class TestConflictDetection:
    """Test conflict detection and reconciliation."""

    def test_type_mismatch_detected(self, enricher):
        """Test that type mismatches are detected."""
        prop = {
            "minimum": 10,  # For numeric types
            "minLength": 5,  # For string types
        }

        enricher._reconcile_conflicts(prop)

        # Conflict should be detected
        assert enricher.stats.conflicts_detected > 0

    def test_format_and_pattern_allowed(self, enricher):
        """Test that format and pattern together are allowed."""
        prop = {
            "format": "email",
            "pattern": "^[a-z]+@example.com$",
        }

        enricher._reconcile_conflicts(prop)

        # No conflict, both are valid together
        assert "format" in prop
        assert "pattern" in prop


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_spec(self, enricher):
        """Test enriching empty spec."""
        result = enricher.enrich_spec({})
        assert result == {}

    def test_spec_without_schemas(self, enricher):
        """Test enriching spec without schemas section."""
        spec = {"info": {"title": "Test API"}, "paths": {}}
        result = enricher.enrich_spec(spec)
        assert result is not None

    def test_null_values_handled(self, enricher):
        """Test that null values are handled safely."""
        spec = {
            "components": {
                "schemas": {
                    "Test": {
                        "type": "object",
                        "properties": {
                            "email": None,
                        },
                    },
                },
            },
        }

        result = enricher.enrich_spec(spec)
        # Should not raise
        assert result["components"]["schemas"]["Test"]["properties"]["email"] is None

    def test_property_with_no_type(self, enricher):
        """Test enriching property with no type specified."""
        prop = {"minLength": 1}  # No type field
        enricher._apply_type_defaults(prop)

        # Should handle gracefully
        assert "minLength" in prop


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
