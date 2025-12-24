"""Unit tests for CLIMetadataEnricher."""

from pathlib import Path

import pytest

from scripts.utils.cli_metadata_enricher import CLIMetadataEnricher


@pytest.fixture
def enricher():
    """Create enricher with default config."""
    return CLIMetadataEnricher()


@pytest.fixture
def simple_spec():
    """Create a simple OpenAPI spec for testing."""
    return {
        "components": {
            "schemas": {
                "Config": {
                    "type": "object",
                    "properties": {
                        "namespace": {"type": "string"},
                        "labels": {"type": "object"},
                        "file": {"type": "string"},
                        "name": {"type": "string"},
                        "id": {"type": "string"},
                    },
                },
            },
        },
    }


class TestCLIMetadataEnricherBasics:
    """Test basic enricher functionality."""

    def test_initialization(self):
        """Test enricher initializes with default config."""
        enricher = CLIMetadataEnricher()
        assert len(enricher.completion_patterns) > 0
        assert len(enricher._compiled_patterns) > 0

    def test_config_loading_missing_file(self):
        """Test enricher loads defaults when config file missing."""
        enricher = CLIMetadataEnricher(config_path=Path("/nonexistent/path.yaml"))
        assert len(enricher.completion_patterns) > 0

    def test_stats_initialization(self):
        """Test enrichment stats start at zero."""
        enricher = CLIMetadataEnricher()
        stats = enricher.get_stats()
        assert stats["help_added"] == 0
        assert stats["examples_added"] == 0
        assert stats["completions_added"] == 0


class TestCompletionTypeDetection:
    """Test completion type detection."""

    def test_namespace_completion(self, enricher):
        """Test namespace field gets list completion."""
        completion = enricher._find_completion_type("namespace")
        assert completion == "namespace-list"

    def test_labels_completion(self, enricher):
        """Test labels field gets key-value completion."""
        completion = enricher._find_completion_type("labels")
        assert completion == "key-value-pairs"

    def test_tags_completion(self, enricher):
        """Test tags field gets key-value completion."""
        completion = enricher._find_completion_type("tags")
        assert completion == "key-value-pairs"

    def test_file_completion(self, enricher):
        """Test file field gets file-path completion."""
        completion = enricher._find_completion_type("file")
        assert completion == "file-path"

    def test_path_completion(self, enricher):
        """Test path field gets file-path completion."""
        completion = enricher._find_completion_type("path")
        assert completion == "file-path"

    def test_unmatched_field_no_completion(self, enricher):
        """Test that unmatched fields don't get completion."""
        completion = enricher._find_completion_type("id")
        assert completion is None


class TestHelpTextGeneration:
    """Test help text generation."""

    def test_namespace_help(self, enricher):
        """Test namespace field gets help text."""
        help_text = enricher._generate_help("namespace")
        assert help_text is not None
        assert "namespace" in help_text.lower()

    def test_labels_help(self, enricher):
        """Test labels field gets help text."""
        help_text = enricher._generate_help("labels")
        assert help_text is not None
        assert "label" in help_text.lower()

    def test_file_help(self, enricher):
        """Test file field gets help text."""
        help_text = enricher._generate_help("file")
        assert help_text is not None

    def test_unmatched_field_no_help(self, enricher):
        """Test that unmatched fields don't get help."""
        help_text = enricher._generate_help("value")
        assert help_text is None


class TestCLIExampleGeneration:
    """Test CLI example generation."""

    def test_namespace_example(self, enricher):
        """Test namespace field gets example."""
        prop = {"type": "string"}
        example = enricher._generate_cli_example("namespace", prop)
        assert example == "default"

    def test_labels_example(self, enricher):
        """Test labels field gets key-value example."""
        prop = {"type": "object"}
        example = enricher._generate_cli_example("labels", prop)
        assert example is not None
        assert "=" in example

    def test_file_example(self, enricher):
        """Test file field gets file path example."""
        prop = {"type": "string"}
        example = enricher._generate_cli_example("file", prop)
        assert example is not None
        assert "." in example  # Has file extension

    def test_enum_value_example(self, enricher):
        """Test enum field gets first enum value as example."""
        prop = {"type": "string", "enum": ["active", "inactive", "pending"]}
        example = enricher._generate_cli_example("status", prop)
        assert example == "active"

    def test_unmatched_field_no_example(self, enricher):
        """Test that unmatched fields don't get examples."""
        prop = {"type": "string"}
        example = enricher._generate_cli_example("id", prop)
        assert example is None


class TestPropertyEnrichment:
    """Test property-level enrichment."""

    def test_property_with_no_cli_metadata(self, enricher):
        """Test enriching property with no CLI metadata."""
        prop = {"type": "string"}
        enricher._enrich_property(prop, "namespace")

        assert "x-ves-cli-help" in prop
        assert "x-ves-cli-completion" in prop

    def test_property_preserves_existing_metadata(self, enricher):
        """Test that existing CLI metadata is preserved."""
        prop = {
            "type": "string",
            "x-ves-cli-help": "Custom help text",
        }
        enricher._enrich_property(prop, "namespace")

        # Existing help should be preserved
        assert prop["x-ves-cli-help"] == "Custom help text"

    def test_stats_tracked_on_enrichment(self, enricher):
        """Test that stats are updated during enrichment."""
        prop = {"type": "string"}
        enricher._enrich_property(prop, "namespace")

        stats = enricher.get_stats()
        assert stats["help_added"] > 0
        assert stats["completions_added"] > 0

    def test_comprehensive_property_enrichment(self, enricher):
        """Test comprehensive enrichment of a property."""
        prop = {"type": "object"}
        enricher._enrich_property(prop, "labels")

        # Should have help, example, and completion
        assert "x-ves-cli-help" in prop
        assert "x-ves-cli-example" in prop
        assert "x-ves-cli-completion" in prop


class TestSpecEnrichment:
    """Test full specification enrichment."""

    def test_enrich_simple_spec(self, enricher, simple_spec):
        """Test enriching a simple OpenAPI spec."""
        result = enricher.enrich_spec(simple_spec)

        # Check that spec structure is preserved
        assert "components" in result
        assert "schemas" in result["components"]
        assert "Config" in result["components"]["schemas"]

        # Check that namespace field was enriched
        config_props = result["components"]["schemas"]["Config"]["properties"]
        namespace_prop = config_props["namespace"]
        assert "x-ves-cli-help" in namespace_prop
        assert "x-ves-cli-completion" in namespace_prop

        # Check that labels field was enriched
        labels_prop = config_props["labels"]
        assert "x-ves-cli-help" in labels_prop
        assert "x-ves-cli-completion" in labels_prop

        # Check that unmatched id field wasn't enriched
        id_prop = config_props["id"]
        assert "x-ves-cli-help" not in id_prop

    def test_stats_after_full_enrichment(self, enricher, simple_spec):
        """Test that stats are updated on full enrichment."""
        enricher.enrich_spec(simple_spec)
        stats = enricher.get_stats()

        assert stats["schemas_processed"] > 0
        assert stats["properties_processed"] > 0
        assert stats["help_added"] > 0

    def test_nested_schemas_processed(self, enricher):
        """Test that nested schemas are processed."""
        spec = {
            "components": {
                "schemas": {
                    "Nested": {
                        "type": "object",
                        "properties": {
                            "namespace": {"type": "string"},
                            "labels": {"type": "object"},
                        },
                    },
                    "Parent": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "config": {"$ref": "#/components/schemas/Nested"},
                        },
                    },
                },
            },
        }

        result = enricher.enrich_spec(spec)
        stats = enricher.get_stats()

        # Both schemas should be processed
        assert stats["schemas_processed"] >= 2

        # Namespace field should be enriched
        namespace_prop = result["components"]["schemas"]["Nested"]["properties"]["namespace"]
        assert "x-ves-cli-completion" in namespace_prop


class TestRequiredFieldDetection:
    """Test required field detection."""

    def test_explicit_required_flag(self, enricher):
        """Test detecting explicit required flag."""
        prop = {"required": True}
        assert enricher._is_required(prop) is True

    def test_no_required_flag(self, enricher):
        """Test field without required flag."""
        prop = {"type": "string"}
        assert enricher._is_required(prop) is False

    def test_discovery_required_flag(self, enricher):
        """Test detecting required from discovery data."""
        prop = {
            "type": "string",
            "x-ves-validation-rules": {"required": True},
        }
        assert enricher._is_required(prop) is True


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
                            "namespace": None,
                        },
                    },
                },
            },
        }

        result = enricher.enrich_spec(spec)
        # Should not raise
        assert result["components"]["schemas"]["Test"]["properties"]["namespace"] is None

    def test_empty_enum(self, enricher):
        """Test handling empty enum."""
        prop = {"type": "string", "enum": []}
        example = enricher._generate_cli_example("status", prop)
        # Should handle gracefully
        assert example is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
