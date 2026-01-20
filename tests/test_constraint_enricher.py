#!/usr/bin/env python3
"""
Unit tests for ConstraintEnricher

Tests cover:
- Pattern matching (string, array, numeric)
- Constraint extraction for each type
- Reconciliation priority (EXISTING > DISCOVERY > INFERRED)
- Edge cases and error handling
- Statistics collection

Target coverage: 80%+
"""

# Import the constraint enricher
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.utils.constraint_enricher import (
    ArrayConstraintExtractor,
    ConstraintEnricher,
    ConstraintReconciler,
    NumericConstraintExtractor,
    ObjectConstraintExtractor,
    PatternMatcher,
    StringConstraintExtractor,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def test_config():
    """Load test constraint patterns configuration"""
    config_path = Path(__file__).parent.parent / "config" / "constraint_patterns.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


@pytest.fixture
def pattern_matcher(test_config):
    """Create PatternMatcher instance"""
    return PatternMatcher(test_config)


@pytest.fixture
def enricher(test_config):
    """Create ConstraintEnricher instance"""
    config_path = Path(__file__).parent.parent / "config" / "constraint_patterns.yaml"
    return ConstraintEnricher(config_path=config_path)


# =============================================================================
# PatternMatcher Tests
# =============================================================================


class TestPatternMatcher:
    """Test pattern matching functionality"""

    def test_match_string_name_pattern(self, pattern_matcher):
        """Test matching 'name' field against string patterns"""
        result = pattern_matcher.match_string_pattern("name")
        assert result is not None
        assert result["description"] == "DNS label format resource name"
        assert result["metadata"]["confidence"] == 0.95

    def test_match_string_email_pattern(self, pattern_matcher):
        """Test matching 'email' field against string patterns"""
        result = pattern_matcher.match_string_pattern("email")
        assert result is not None
        assert result["constraints"]["format"] == "email"
        assert result["metadata"]["category"] == "communication"

    def test_match_string_uuid_pattern(self, pattern_matcher):
        """Test matching 'uuid' field against string patterns"""
        result = pattern_matcher.match_string_pattern("uuid")
        assert result is not None
        assert result["constraints"]["minLength"] == 36
        assert result["constraints"]["maxLength"] == 36
        assert result["metadata"]["confidence"] == 0.99

    def test_match_string_no_match(self, pattern_matcher):
        """Test field with no matching pattern"""
        result = pattern_matcher.match_string_pattern("unknown_field_xyz")
        assert result is None

    def test_match_array_origins_pattern(self, pattern_matcher):
        """Test matching 'origins' field against array patterns"""
        result = pattern_matcher.match_array_pattern("origins")
        assert result is not None
        assert result["constraints"]["minItems"] == 1
        assert result["constraints"]["maxItems"] == 50

    def test_match_array_tags_pattern(self, pattern_matcher):
        """Test matching 'tags' field against array patterns"""
        result = pattern_matcher.match_array_pattern("tags")
        assert result is not None
        assert result["constraints"]["maxItems"] == 100

    def test_match_number_port_pattern(self, pattern_matcher):
        """Test matching 'port' field against numeric patterns"""
        result = pattern_matcher.match_number_pattern("port")
        assert result is not None
        assert result["constraints"]["minimum"] == 1
        assert result["constraints"]["maximum"] == 65535
        assert result["metadata"]["confidence"] == 0.99

    def test_match_number_timeout_pattern(self, pattern_matcher):
        """Test matching 'timeout' field against numeric patterns"""
        result = pattern_matcher.match_number_pattern("timeout")
        assert result is not None
        assert result["constraints"]["minimum"] == 1
        assert result["constraints"]["maximum"] == 3600

    def test_match_number_vlan_id_pattern(self, pattern_matcher):
        """Test matching 'vlan_id' field against numeric patterns"""
        result = pattern_matcher.match_number_pattern("vlan_id")
        assert result is not None
        assert result["constraints"]["minimum"] == 1
        assert result["constraints"]["maximum"] == 4094
        assert result["metadata"]["confidence"] == 0.95

    def test_pattern_case_insensitive(self, pattern_matcher):
        """Test patterns are case-insensitive"""
        result1 = pattern_matcher.match_string_pattern("name")
        result2 = pattern_matcher.match_string_pattern("NAME")
        result3 = pattern_matcher.match_string_pattern("Name")
        assert result1 is not None
        assert result2 is not None
        assert result3 is not None


# =============================================================================
# StringConstraintExtractor Tests
# =============================================================================


class TestStringConstraintExtractor:
    """Test string constraint extraction"""

    def test_extract_from_existing_schema(self):
        """Test extraction from schema with existing constraints"""
        schema = {
            "type": "string",
            "minLength": 1,
            "maxLength": 100,
            "pattern": "^[a-z]+$",
        }
        result = StringConstraintExtractor.extract("test_field", schema, None)
        assert result is not None
        assert result["minLength"] == 1
        assert result["maxLength"] == 100
        assert result["pattern"] == "^[a-z]+$"

    def test_extract_from_pattern_match(self, pattern_matcher):
        """Test extraction from pattern match only"""
        schema = {"type": "string"}
        pattern_match = pattern_matcher.match_string_pattern("name")
        result = StringConstraintExtractor.extract("name", schema, pattern_match)
        assert result is not None
        assert result["minLength"] == 1
        assert result["maxLength"] == 63
        assert "pattern" in result

    def test_extract_schema_overrides_pattern(self, pattern_matcher):
        """Test that existing schema values take precedence"""
        schema = {
            "type": "string",
            "minLength": 10,  # Different from pattern
            "maxLength": 50,  # Different from pattern
        }
        pattern_match = pattern_matcher.match_string_pattern("name")
        result = StringConstraintExtractor.extract("name", schema, pattern_match)
        assert result is not None
        assert result["minLength"] == 10  # Schema value preserved
        assert result["maxLength"] == 50  # Schema value preserved

    def test_extract_no_constraints(self):
        """Test extraction when no constraints available"""
        schema = {"type": "string"}
        result = StringConstraintExtractor.extract("test_field", schema, None)
        assert result is None


# =============================================================================
# ArrayConstraintExtractor Tests
# =============================================================================


class TestArrayConstraintExtractor:
    """Test array constraint extraction"""

    def test_extract_from_existing_schema(self):
        """Test extraction from schema with existing constraints"""
        schema = {
            "type": "array",
            "minItems": 1,
            "maxItems": 10,
            "uniqueItems": True,
        }
        result = ArrayConstraintExtractor.extract("test_field", schema, None)
        assert result is not None
        assert result["minItems"] == 1
        assert result["maxItems"] == 10
        assert result["uniqueItems"] is True

    def test_extract_from_pattern_match(self, pattern_matcher):
        """Test extraction from pattern match only"""
        schema = {"type": "array"}
        pattern_match = pattern_matcher.match_array_pattern("origins")
        result = ArrayConstraintExtractor.extract("origins", schema, pattern_match)
        assert result is not None
        assert result["minItems"] == 1
        assert result["maxItems"] == 50

    def test_extract_no_constraints(self):
        """Test extraction when no constraints available"""
        schema = {"type": "array"}
        result = ArrayConstraintExtractor.extract("test_field", schema, None)
        assert result is None


# =============================================================================
# NumericConstraintExtractor Tests
# =============================================================================


class TestNumericConstraintExtractor:
    """Test numeric constraint extraction"""

    def test_extract_from_existing_schema(self):
        """Test extraction from schema with existing constraints"""
        schema = {
            "type": "integer",
            "minimum": 1,
            "maximum": 100,
            "multipleOf": 5,
        }
        result = NumericConstraintExtractor.extract("test_field", schema, None)
        assert result is not None
        assert result["minimum"] == 1
        assert result["maximum"] == 100
        assert result["multipleOf"] == 5

    def test_extract_from_pattern_match(self, pattern_matcher):
        """Test extraction from pattern match only"""
        schema = {"type": "integer"}
        pattern_match = pattern_matcher.match_number_pattern("port")
        result = NumericConstraintExtractor.extract("port", schema, pattern_match)
        assert result is not None
        assert result["minimum"] == 1
        assert result["maximum"] == 65535

    def test_extract_no_constraints(self):
        """Test extraction when no constraints available"""
        schema = {"type": "integer"}
        result = NumericConstraintExtractor.extract("test_field", schema, None)
        assert result is None


# =============================================================================
# ObjectConstraintExtractor Tests
# =============================================================================


class TestObjectConstraintExtractor:
    """Test object constraint extraction"""

    def test_extract_from_existing_schema(self):
        """Test extraction from schema with existing constraints"""
        schema = {
            "type": "object",
            "minProperties": 1,
            "maxProperties": 10,
            "required": ["field1", "field2"],
        }
        result = ObjectConstraintExtractor.extract("test_field", schema)
        assert result is not None
        assert result["minProperties"] == 1
        assert result["maxProperties"] == 10
        assert result["required"] == ["field1", "field2"]

    def test_extract_no_constraints(self):
        """Test extraction when no constraints available"""
        schema = {"type": "object"}
        result = ObjectConstraintExtractor.extract("test_field", schema)
        assert result is None


# =============================================================================
# ConstraintReconciler Tests
# =============================================================================


class TestConstraintReconciler:
    """Test constraint reconciliation logic"""

    def test_existing_takes_priority(self):
        """Test that existing constraints are preserved"""
        existing = {
            "type": "string",
            "string": {"minLength": 10},
            "metadata": {"source": "existing", "confidence": 1.0},
        }
        discovery = {
            "type": "string",
            "string": {"minLength": 5},
        }
        inferred = {
            "type": "string",
            "string": {"minLength": 1},
        }

        result = ConstraintReconciler.reconcile(existing, discovery, inferred)
        assert result == existing

    def test_discovery_overrides_inferred(self):
        """Test that discovery data overrides inferred"""
        discovery = {
            "type": "string",
            "string": {"minLength": 5},
        }
        inferred = {
            "type": "string",
            "string": {"minLength": 1},
            "metadata": {"source": "inferred", "confidence": 0.85},
        }

        result = ConstraintReconciler.reconcile(None, discovery, inferred)
        assert result is not None
        assert result["metadata"]["source"] == "discovery"
        assert result["metadata"]["confidence"] == 0.99

    def test_inferred_only(self):
        """Test reconciliation with only inferred data"""
        inferred = {
            "type": "string",
            "string": {"minLength": 1},
            "metadata": {"source": "inferred", "confidence": 0.85},
        }

        result = ConstraintReconciler.reconcile(None, None, inferred)
        assert result is not None
        assert result["metadata"]["source"] == "inferred"
        assert result["metadata"]["confidence"] == 0.85

    def test_deterministic_flag_high_confidence(self):
        """Test deterministic flag for high confidence"""
        inferred = {
            "type": "string",
            "string": {"minLength": 1},
            "metadata": {"source": "inferred", "confidence": 0.95},
        }

        result = ConstraintReconciler.reconcile(None, None, inferred, confidence_threshold=0.9)
        assert result is not None
        assert result.get("deterministic") is True

    def test_deterministic_flag_low_confidence(self):
        """Test no deterministic flag for low confidence"""
        inferred = {
            "type": "string",
            "string": {"minLength": 1},
            "metadata": {"source": "inferred", "confidence": 0.75},
        }

        result = ConstraintReconciler.reconcile(None, None, inferred, confidence_threshold=0.9)
        assert result is not None
        assert "deterministic" not in result or result.get("deterministic") is False

    def test_no_constraints(self):
        """Test reconciliation with no constraints"""
        result = ConstraintReconciler.reconcile(None, None, None)
        assert result is None


# =============================================================================
# ConstraintEnricher Integration Tests
# =============================================================================


class TestConstraintEnricher:
    """Test the complete enrichment process"""

    def test_enrich_string_property(self, enricher):
        """Test enriching a string property"""
        spec = {
            "components": {
                "schemas": {
                    "TestSchema": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                            },
                        },
                    },
                },
            },
        }

        enriched = enricher.enrich_spec(spec)
        name_property = enriched["components"]["schemas"]["TestSchema"]["properties"]["name"]

        assert "x-f5xc-constraints" in name_property
        constraints = name_property["x-f5xc-constraints"]
        assert constraints["type"] == "string"
        assert "string" in constraints
        assert constraints["string"]["minLength"] == 1
        assert constraints["string"]["maxLength"] == 63

    def test_enrich_array_property(self, enricher):
        """Test enriching an array property"""
        spec = {
            "components": {
                "schemas": {
                    "TestSchema": {
                        "type": "object",
                        "properties": {
                            "origins": {
                                "type": "array",
                            },
                        },
                    },
                },
            },
        }

        enriched = enricher.enrich_spec(spec)
        origins_property = enriched["components"]["schemas"]["TestSchema"]["properties"]["origins"]

        assert "x-f5xc-constraints" in origins_property
        constraints = origins_property["x-f5xc-constraints"]
        assert constraints["type"] == "array"
        assert "array" in constraints
        assert constraints["array"]["minItems"] == 1
        assert constraints["array"]["maxItems"] == 50

    def test_enrich_number_property(self, enricher):
        """Test enriching a numeric property"""
        spec = {
            "components": {
                "schemas": {
                    "TestSchema": {
                        "type": "object",
                        "properties": {
                            "port": {
                                "type": "integer",
                            },
                        },
                    },
                },
            },
        }

        enriched = enricher.enrich_spec(spec)
        port_property = enriched["components"]["schemas"]["TestSchema"]["properties"]["port"]

        assert "x-f5xc-constraints" in port_property
        constraints = port_property["x-f5xc-constraints"]
        assert constraints["type"] == "number"
        assert "number" in constraints
        assert constraints["number"]["minimum"] == 1
        assert constraints["number"]["maximum"] == 65535

    def test_skip_existing_constraints(self, enricher):
        """Test that existing x-f5xc-constraints are preserved"""
        spec = {
            "components": {
                "schemas": {
                    "TestSchema": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "x-f5xc-constraints": {
                                    "type": "string",
                                    "string": {"minLength": 100},  # Different value
                                    "metadata": {"source": "existing", "confidence": 1.0},
                                },
                            },
                        },
                    },
                },
            },
        }

        enriched = enricher.enrich_spec(spec)
        name_property = enriched["components"]["schemas"]["TestSchema"]["properties"]["name"]

        # Original constraint preserved
        assert name_property["x-f5xc-constraints"]["string"]["minLength"] == 100
        assert name_property["x-f5xc-constraints"]["metadata"]["source"] == "existing"

    def test_statistics_collection(self, enricher):
        """Test that statistics are collected correctly"""
        spec = {
            "components": {
                "schemas": {
                    "TestSchema": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "email": {"type": "string"},
                            "port": {"type": "integer"},
                            "tags": {"type": "array"},
                        },
                    },
                },
            },
        }

        enriched = enricher.enrich_spec(spec)
        stats = enricher.get_stats()

        assert stats["properties_analyzed"] == 4
        assert stats["constraints_added"] > 0
        assert stats["string_constraints"] >= 2
        assert stats["array_constraints"] >= 1
        assert stats["number_constraints"] >= 1
        assert stats["coverage_percentage"] > 0


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_spec(self, enricher):
        """Test enriching an empty spec"""
        spec = {}
        result = enricher.enrich_spec(spec)
        assert result == {}

    def test_spec_without_schemas(self, enricher):
        """Test spec without components.schemas"""
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0.0"},
        }
        result = enricher.enrich_spec(spec)
        stats = enricher.get_stats()
        assert stats["properties_analyzed"] == 0

    def test_schema_without_properties(self, enricher):
        """Test schema without properties"""
        spec = {
            "components": {
                "schemas": {
                    "TestSchema": {
                        "type": "object",
                    },
                },
            },
        }
        result = enricher.enrich_spec(spec)
        stats = enricher.get_stats()
        assert stats["properties_analyzed"] == 0

    def test_unknown_field_type(self, enricher):
        """Test property with unknown type"""
        spec = {
            "components": {
                "schemas": {
                    "TestSchema": {
                        "type": "object",
                        "properties": {
                            "unknown": {
                                # No type field
                            },
                        },
                    },
                },
            },
        }
        enriched = enricher.enrich_spec(spec)
        unknown_property = enriched["components"]["schemas"]["TestSchema"]["properties"]["unknown"]
        assert "x-f5xc-constraints" not in unknown_property


# =============================================================================
# Pattern Coverage Tests
# =============================================================================


class TestPatternCoverage:
    """Test coverage of various patterns"""

    @pytest.mark.parametrize(
        "field_name,expected_category",
        [
            ("username", "identity"),
            ("email", "communication"),
            ("phone", "communication"),
            ("uuid", "identifier"),
            ("timestamp", "temporal"),
            ("date", "temporal"),
            ("certificate", "crypto"),
            ("private_key", "crypto"),
            ("description", "content"),
            ("path", "content"),
        ],
    )
    def test_string_pattern_categories(self, pattern_matcher, field_name, expected_category):
        """Test string patterns match correct categories"""
        result = pattern_matcher.match_string_pattern(field_name)
        assert result is not None
        assert result["metadata"]["category"] == expected_category

    @pytest.mark.parametrize(
        "field_name",
        [
            "servers",
            "pools",
            "origins",
            "tags",
            "domains",
            "items",
            "rules",
            "ips",
            "hosts",
            "headers",
        ],
    )
    def test_array_pattern_coverage(self, pattern_matcher, field_name):
        """Test array patterns are matched"""
        result = pattern_matcher.match_array_pattern(field_name)
        assert result is not None
        assert "constraints" in result

    @pytest.mark.parametrize(
        "field_name",
        [
            "port",
            "vlan_id",
            "timeout",
            "interval",
            "retries",
            "delay",
            "weight",
            "priority",
            "threshold",
            "limit",
        ],
    )
    def test_number_pattern_coverage(self, pattern_matcher, field_name):
        """Test numeric patterns are matched"""
        result = pattern_matcher.match_number_pattern(field_name)
        assert result is not None
        assert "constraints" in result


if __name__ == "__main__":
    pytest.main(
        [__file__, "-v", "--cov=scripts.utils.constraint_enricher", "--cov-report=term-missing"],
    )
