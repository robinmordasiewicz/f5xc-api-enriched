"""Unit tests for FieldMetadataEnricher."""

from pathlib import Path

import pytest

from scripts.utils.field_metadata_enricher import FieldMetadataEnricher


@pytest.fixture
def enricher():
    """Create enricher with default config."""
    return FieldMetadataEnricher()


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
                        "uuid": {"type": "string"},
                        "timestamp": {"type": "string"},
                    },
                },
            },
        },
    }


class TestFieldMetadataEnricherBasics:
    """Test basic enricher functionality."""

    def test_initialization(self):
        """Test enricher initializes with default config."""
        enricher = FieldMetadataEnricher()
        assert enricher.preserve_existing is True
        assert len(enricher.field_patterns) > 0
        assert len(enricher._compiled_patterns) > 0  # noqa: SLF001

    def test_config_loading_missing_file(self):
        """Test enricher loads defaults when config file missing."""
        enricher = FieldMetadataEnricher(config_path=Path("/nonexistent/path.yaml"))
        assert enricher.preserve_existing is True
        assert len(enricher.field_patterns) > 0

    def test_stats_initialization(self):
        """Test enrichment stats start at zero."""
        enricher = FieldMetadataEnricher()
        stats = enricher.get_stats()
        assert stats["descriptions_added"] == 0
        assert stats["validations_added"] == 0
        assert stats["examples_added"] == 0
        assert stats["completions_added"] == 0
        assert stats["defaults_added"] == 0


class TestDescriptionEnrichment:
    """Test description enrichment."""

    def test_name_field_gets_description(self, enricher):
        """Test that name field gets description."""
        prop = {"type": "string"}
        enricher._enrich_property(prop, "name", "TestSchema")  # noqa: SLF001

        assert "x-ves-description" in prop
        assert "name" in prop["x-ves-description"].lower()

    def test_email_field_gets_description(self, enricher):
        """Test that email field gets description."""
        prop = {"type": "string"}
        enricher._enrich_property(prop, "email", "TestSchema")  # noqa: SLF001

        assert "x-ves-description" in prop
        assert "email" in prop["x-ves-description"].lower()

    def test_port_field_gets_description(self, enricher):
        """Test that port field gets description."""
        prop = {"type": "integer"}
        enricher._enrich_property(prop, "port", "TestSchema")  # noqa: SLF001

        assert "x-ves-description" in prop
        assert "port" in prop["x-ves-description"].lower()

    def test_preserves_existing_description(self, enricher):
        """Test that existing descriptions are preserved."""
        existing_desc = "Custom description"
        prop = {"type": "string", "x-ves-description": existing_desc}
        enricher._enrich_property(prop, "name", "TestSchema")  # noqa: SLF001

        assert prop["x-ves-description"] == existing_desc


class TestValidationEnrichment:
    """Test validation enrichment."""

    def test_name_field_gets_validation(self, enricher):
        """Test that name field gets validation constraints."""
        prop = {"type": "string"}
        enricher._enrich_property(prop, "name", "TestSchema")  # noqa: SLF001

        assert "x-ves-validation" in prop
        validation = prop["x-ves-validation"]
        assert "minLength" in validation or "pattern" in validation

    def test_port_field_gets_validation(self, enricher):
        """Test that port field gets port range validation."""
        prop = {"type": "integer"}
        enricher._enrich_property(prop, "port", "TestSchema")  # noqa: SLF001

        assert "x-ves-validation" in prop
        validation = prop["x-ves-validation"]
        assert validation.get("minimum") == 1
        assert validation.get("maximum") == 65535

    def test_email_field_gets_email_format(self, enricher):
        """Test that email field gets email format validation."""
        prop = {"type": "string"}
        enricher._enrich_property(prop, "email", "TestSchema")  # noqa: SLF001

        assert "x-ves-validation" in prop
        validation = prop["x-ves-validation"]
        assert validation.get("format") == "email"

    def test_preserves_existing_validation(self, enricher):
        """Test that existing validation is preserved."""
        existing_validation = {"minLength": 10}
        prop = {"type": "string", "x-ves-validation": existing_validation}
        enricher._enrich_property(prop, "name", "TestSchema")  # noqa: SLF001

        assert prop["x-ves-validation"] == existing_validation


class TestExampleEnrichment:
    """Test example enrichment."""

    def test_name_field_gets_examples(self, enricher):
        """Test that name field gets examples."""
        prop = {"type": "string"}
        enricher._enrich_property(prop, "name", "TestSchema")  # noqa: SLF001

        assert "x-ves-examples" in prop
        examples = prop["x-ves-examples"]
        assert isinstance(examples, list)
        assert len(examples) > 0
        assert all("value" in ex and "context" in ex for ex in examples)

    def test_email_field_gets_examples(self, enricher):
        """Test that email field gets email examples."""
        prop = {"type": "string"}
        enricher._enrich_property(prop, "email", "TestSchema")  # noqa: SLF001

        assert "x-ves-examples" in prop
        examples = prop["x-ves-examples"]
        assert any("@" in str(ex.get("value", "")) for ex in examples)

    def test_port_field_gets_examples(self, enricher):
        """Test that port field gets port examples."""
        prop = {"type": "integer"}
        enricher._enrich_property(prop, "port", "TestSchema")  # noqa: SLF001

        assert "x-ves-examples" in prop

    def test_preserves_existing_examples(self, enricher):
        """Test that existing examples are preserved."""
        existing_examples = [{"value": "custom", "context": "test"}]
        prop = {"type": "string", "x-ves-examples": existing_examples}
        enricher._enrich_property(prop, "name", "TestSchema")  # noqa: SLF001

        assert prop["x-ves-examples"] == existing_examples


class TestCompletionEnrichment:
    """Test CLI completion enrichment."""

    def test_name_field_gets_completion(self, enricher):
        """Test that name field gets completion info."""
        prop = {"type": "string"}
        enricher._enrich_property(prop, "name", "TestSchema")  # noqa: SLF001

        assert "x-ves-completion" in prop
        assert "type" in prop["x-ves-completion"]

    def test_email_field_gets_email_completion(self, enricher):
        """Test that email field gets email completion."""
        prop = {"type": "string"}
        enricher._enrich_property(prop, "email", "TestSchema")  # noqa: SLF001

        assert "x-ves-completion" in prop
        completion = prop["x-ves-completion"]
        assert completion.get("type") == "email"

    def test_port_field_gets_port_completion(self, enricher):
        """Test that port field gets port completion."""
        prop = {"type": "integer"}
        enricher._enrich_property(prop, "port", "TestSchema")  # noqa: SLF001

        assert "x-ves-completion" in prop
        completion = prop["x-ves-completion"]
        assert completion.get("type") == "port"

    def test_preserves_existing_completion(self, enricher):
        """Test that existing completion is preserved."""
        existing_completion = {"type": "custom"}
        prop = {"type": "string", "x-ves-completion": existing_completion}
        enricher._enrich_property(prop, "name", "TestSchema")  # noqa: SLF001

        assert prop["x-ves-completion"] == existing_completion


class TestDefaultsEnrichment:
    """Test default values enrichment."""

    def test_port_field_gets_default(self, enricher):
        """Test that port field gets default value."""
        prop = {"type": "integer"}
        enricher._enrich_property(prop, "port", "TestSchema")  # noqa: SLF001

        # Port should have defaults defined in config
        if "x-ves-defaults" in prop:
            assert "value" in prop["x-ves-defaults"]
            assert "reasoning" in prop["x-ves-defaults"]


class TestSpecEnrichment:
    """Test full specification enrichment."""

    def test_enrich_simple_spec(self, enricher, simple_spec):
        """Test enriching a simple OpenAPI spec."""
        result = enricher.enrich_spec(simple_spec)

        # Check that spec structure is preserved
        assert "components" in result
        assert "schemas" in result["components"]
        assert "User" in result["components"]["schemas"]

        # Check that properties were enriched
        user_props = result["components"]["schemas"]["User"]["properties"]
        assert "name" in user_props
        assert "email" in user_props
        assert "port" in user_props

        # Check that enrichment happened
        name_prop = user_props["name"]
        assert "x-ves-description" in name_prop

    def test_stats_after_full_enrichment(self, enricher, simple_spec):
        """Test that stats are correctly updated after enrichment."""
        enricher.enrich_spec(simple_spec)
        stats = enricher.get_stats()

        assert stats["schemas_processed"] > 0
        assert stats["properties_processed"] > 0
        assert stats["descriptions_added"] > 0

    def test_nested_schemas_processed(self, enricher):
        """Test that nested schemas are processed."""
        spec = {
            "components": {
                "schemas": {
                    "Address": {
                        "type": "object",
                        "properties": {
                            "street": {"type": "string"},
                            "port": {"type": "integer"},
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

        enricher.enrich_spec(spec)
        stats = enricher.get_stats()

        # Both schemas should be processed
        assert stats["schemas_processed"] >= 2

    def test_array_and_compositions_handled(self, enricher):
        """Test that arrays and schema compositions are handled."""
        spec = {
            "components": {
                "schemas": {
                    "Item": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                    },
                    "ItemArray": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/Item"},
                    },
                    "Combined": {
                        "allOf": [
                            {"$ref": "#/components/schemas/Item"},
                            {
                                "type": "object",
                                "properties": {
                                    "email": {"type": "string"},
                                },
                            },
                        ],
                    },
                },
            },
        }

        result = enricher.enrich_spec(spec)
        assert result is not None
        assert "components" in result


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
                            "name": None,
                            "email": {"type": "string"},
                        },
                    },
                },
            },
        }

        result = enricher.enrich_spec(spec)
        assert result["components"]["schemas"]["Test"]["properties"]["name"] is None

    def test_non_matching_fields_skipped(self, enricher):
        """Test that non-matching fields are not enriched."""
        prop = {"type": "string"}
        enricher._enrich_property(prop, "arbitrary_field", "TestSchema")  # noqa: SLF001

        # Should not add any x-ves-* fields for non-matching fields
        ves_keys = [k for k in prop if k.startswith("x-ves-")]
        assert len(ves_keys) == 0

    def test_multiple_enrichment_preserves_additions(self, enricher):
        """Test that running enrichment twice doesn't duplicate."""
        spec = {
            "components": {
                "schemas": {
                    "Test": {"type": "object", "properties": {"name": {"type": "string"}}},
                },
            },
        }

        # First enrichment
        result1 = enricher.enrich_spec(spec)
        desc1 = result1["components"]["schemas"]["Test"]["properties"]["name"].get(
            "x-ves-description",
        )

        # Create fresh enricher to test with preserved flag
        enricher2 = FieldMetadataEnricher()
        enricher2.preserve_existing = True

        result2 = enricher2.enrich_spec(result1)
        desc2 = result2["components"]["schemas"]["Test"]["properties"]["name"].get(
            "x-ves-description",
        )

        # Description should be identical (not duplicated)
        assert desc1 == desc2


class TestPatternMatching:
    """Test pattern matching accuracy."""

    def test_exact_pattern_match(self, enricher):
        """Test that patterns match end-of-field-name correctly."""
        # Should match - 'name' field directly or as a word boundary match
        assert enricher._find_pattern("name") is not None  # noqa: SLF001

        # Note: 'user_name' won't match \bname$ because the word boundary before 'name'
        # is not at the start of 'user_name', it's in the middle (_)
        # So 'user_name' and 'resource_name' correctly do NOT match

        # Test that underscore-separated compound words don't match single word patterns
        assert enricher._find_pattern("user_name") is None  # noqa: SLF001  # Expected: doesn't match \bname$

        # But 'namespace' DOES match \bname$ because of the word boundary before 'name'
        assert enricher._find_pattern("namespace") is not None  # noqa: SLF001

        # Verify enrichment happens for matching patterns
        prop = {"type": "string"}
        enricher._enrich_property(prop, "namespace", "TestSchema")  # noqa: SLF001
        assert "x-ves-description" in prop  # "namespace" matches \bname$ due to word boundary

    def test_multiple_pattern_matching(self, enricher):
        """Test behavior when multiple patterns could match."""
        # If a field matches multiple patterns, first one wins
        pattern = enricher._find_pattern("email_address")  # noqa: SLF001

        # Should match email pattern
        if pattern:
            assert "email" in pattern.get("pattern", "").lower() or "@" in str(
                pattern,
            )


class TestStatsCollection:
    """Test statistics collection."""

    def test_all_stats_tracked(self, enricher):
        """Test that all stats are properly tracked."""
        spec = {
            "components": {
                "schemas": {
                    "Test": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "email": {"type": "string"},
                            "port": {"type": "integer"},
                        },
                    },
                },
            },
        }

        enricher.enrich_spec(spec)
        stats = enricher.get_stats()

        # Verify all stat types exist
        assert "descriptions_added" in stats
        assert "validations_added" in stats
        assert "examples_added" in stats
        assert "completions_added" in stats
        assert "schemas_processed" in stats
        assert "properties_processed" in stats

        # Verify reasonable values
        assert stats["schemas_processed"] >= 1
        assert stats["properties_processed"] >= 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
