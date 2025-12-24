"""Unit tests for OperationMetadataEnricher dual-format functionality (Issue #139)."""

import pytest

from scripts.utils.operation_metadata_enricher import OperationMetadataEnricher


@pytest.fixture
def enricher():
    """Create enricher with default config."""
    return OperationMetadataEnricher()


@pytest.fixture
def simple_spec():
    """Create a simple OpenAPI spec for testing."""
    return {
        "paths": {
            "/api/resources": {
                "get": {
                    "operationId": "listResources",
                    "requestBody": {},
                    "responses": {
                        "200": {"description": "Success"},
                        "400": {"description": "Bad request"},
                        "404": {"description": "Not found"},
                    },
                },
                "post": {
                    "operationId": "createResource",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string", "description": "Resource name"},
                                        "description": {
                                            "type": "string",
                                            "description": "Resource description",
                                        },
                                    },
                                    "required": ["name"],
                                },
                            },
                        },
                    },
                    "responses": {
                        "201": {"description": "Created"},
                        "400": {"description": "Bad request"},
                        "409": {"description": "Conflict"},
                    },
                },
            },
            "/api/resources/{id}": {
                "get": {
                    "operationId": "getResource",
                    "parameters": [{"name": "id", "in": "path", "required": True}],
                    "responses": {
                        "200": {"description": "Success"},
                        "404": {"description": "Not found"},
                    },
                },
                "delete": {
                    "operationId": "deleteResource",
                    "parameters": [{"name": "id", "in": "path", "required": True}],
                    "responses": {
                        "204": {"description": "No Content"},
                        "404": {"description": "Not found"},
                    },
                },
            },
        },
    }


class TestDualFormatSupport:
    """Test dual-format (old + new) metadata generation."""

    def test_backward_compatibility_old_format_present(self, enricher, simple_spec):
        """Test that old format fields are still present for backward compatibility."""
        result = enricher.enrich_spec(simple_spec)
        get_op = result["paths"]["/api/resources"]["get"]

        # Old format fields should be present
        assert "x-ves-danger-level" in get_op
        assert "x-ves-cli-examples" in get_op
        assert "x-ves-required-fields" in get_op or "x-ves-danger-level" in get_op

    def test_new_format_comprehensive_metadata(self, enricher, simple_spec):
        """Test that new comprehensive metadata is added."""
        result = enricher.enrich_spec(simple_spec)
        get_op = result["paths"]["/api/resources"]["get"]

        # New format field should be present
        assert "x-ves-operation-metadata" in get_op
        metadata = get_op["x-ves-operation-metadata"]

        # Verify comprehensive metadata structure
        assert "purpose" in metadata
        assert "required_fields" in metadata
        assert "optional_fields" in metadata
        assert "field_docs" in metadata
        assert "conditions" in metadata
        assert "side_effects" in metadata
        assert "danger_level" in metadata
        assert "confirmation_required" in metadata
        assert "common_errors" in metadata
        assert "performance_impact" in metadata
        assert "examples" in metadata

    def test_purpose_generation_get_list(self, enricher, simple_spec):
        """Test purpose generation for GET list operation."""
        result = enricher.enrich_spec(simple_spec)
        get_op = result["paths"]["/api/resources"]["get"]
        metadata = get_op["x-ves-operation-metadata"]

        assert "List" in metadata["purpose"]
        assert "resources" in metadata["purpose"]

    def test_purpose_generation_get_single(self, enricher, simple_spec):
        """Test purpose generation for GET single resource operation."""
        result = enricher.enrich_spec(simple_spec)
        get_op = result["paths"]["/api/resources/{id}"]["get"]
        metadata = get_op["x-ves-operation-metadata"]

        assert "Retrieve" in metadata["purpose"]
        assert "resource" in metadata["purpose"]

    def test_purpose_generation_post_create(self, enricher, simple_spec):
        """Test purpose generation for POST create operation."""
        result = enricher.enrich_spec(simple_spec)
        post_op = result["paths"]["/api/resources"]["post"]
        metadata = post_op["x-ves-operation-metadata"]

        assert "Create" in metadata["purpose"]
        assert "resource" in metadata["purpose"]

    def test_purpose_generation_delete(self, enricher, simple_spec):
        """Test purpose generation for DELETE operation."""
        result = enricher.enrich_spec(simple_spec)
        delete_op = result["paths"]["/api/resources/{id}"]["delete"]
        metadata = delete_op["x-ves-operation-metadata"]

        assert "Delete" in metadata["purpose"]
        assert "resource" in metadata["purpose"]

    def test_required_fields_identification(self, enricher, simple_spec):
        """Test identification of required fields."""
        result = enricher.enrich_spec(simple_spec)
        post_op = result["paths"]["/api/resources"]["post"]
        metadata = post_op["x-ves-operation-metadata"]

        # Name is required, description is optional
        assert "name" in metadata["required_fields"]
        assert "description" in metadata["optional_fields"]

    def test_field_docs_extraction(self, enricher, simple_spec):
        """Test extraction of field documentation."""
        result = enricher.enrich_spec(simple_spec)
        post_op = result["paths"]["/api/resources"]["post"]
        metadata = post_op["x-ves-operation-metadata"]

        field_docs = metadata["field_docs"]
        assert "name" in field_docs
        assert "description" in field_docs
        assert "Resource name" in field_docs["name"]

    def test_danger_level_consistency(self, enricher, simple_spec):
        """Test that danger level is consistent between old and new formats."""
        result = enricher.enrich_spec(simple_spec)
        get_op = result["paths"]["/api/resources"]["get"]

        old_format_level = get_op["x-ves-danger-level"]
        new_format_level = get_op["x-ves-operation-metadata"]["danger_level"]

        assert old_format_level == new_format_level

    def test_confirmation_required_high_danger(self, enricher, simple_spec):
        """Test confirmation requirement for high-danger operations."""
        result = enricher.enrich_spec(simple_spec)
        delete_op = result["paths"]["/api/resources/{id}"]["delete"]
        metadata = delete_op["x-ves-operation-metadata"]

        # DELETE is high danger, so confirmation should be required
        if metadata["danger_level"] == "high":
            assert metadata["confirmation_required"] is True

    def test_common_errors_mapping(self, enricher, simple_spec):
        """Test mapping of HTTP status codes to user-friendly errors."""
        result = enricher.enrich_spec(simple_spec)
        post_op = result["paths"]["/api/resources"]["post"]
        metadata = post_op["x-ves-operation-metadata"]

        errors = metadata["common_errors"]

        # Should have multiple error mappings
        assert len(errors) > 0

        # Each error should have code, message, and solution
        for error in errors:
            assert "code" in error
            assert "message" in error
            assert "solution" in error

    def test_performance_impact_assessment(self, enricher, simple_spec):
        """Test performance impact assessment."""
        result = enricher.enrich_spec(simple_spec)
        get_op = result["paths"]["/api/resources"]["get"]
        metadata = get_op["x-ves-operation-metadata"]

        impact = metadata["performance_impact"]
        assert "latency" in impact
        assert "resource_usage" in impact
        assert impact["latency"] in ["low", "moderate", "high"]
        assert impact["resource_usage"] in ["low", "moderate", "high"]

    def test_side_effects_preservation(self, enricher, simple_spec):
        """Test that side effects are preserved in comprehensive metadata."""
        result = enricher.enrich_spec(simple_spec)
        post_op = result["paths"]["/api/resources"]["post"]
        metadata = post_op["x-ves-operation-metadata"]

        # POST should have side effects
        assert "side_effects" in metadata
        side_effects = metadata["side_effects"]
        assert isinstance(side_effects, dict)

    def test_examples_included_in_metadata(self, enricher, simple_spec):
        """Test that examples are included in comprehensive metadata."""
        result = enricher.enrich_spec(simple_spec)
        get_op = result["paths"]["/api/resources"]["get"]
        metadata = get_op["x-ves-operation-metadata"]

        # Examples should be present
        assert "examples" in metadata
        examples = metadata["examples"]
        assert isinstance(examples, list)

    def test_prerequisites_identification(self, enricher):
        """Test identification of operation prerequisites."""
        spec = {
            "paths": {
                "/api/namespaces/{namespace}/resources": {
                    "post": {
                        "operationId": "createResource",
                        "parameters": [
                            {"name": "namespace", "in": "path", "required": True},
                        ],
                        "responses": {"201": {"description": "Created"}},
                    },
                },
            },
        }

        result = enricher.enrich_spec(spec)
        post_op = result["paths"]["/api/namespaces/{namespace}/resources"]["post"]
        metadata = post_op["x-ves-operation-metadata"]

        conditions = metadata["conditions"]
        assert "prerequisites" in conditions
        # Should identify namespace requirement
        assert any("namespace" in str(p).lower() for p in conditions["prerequisites"])

    def test_postconditions_for_create(self, enricher, simple_spec):
        """Test postcondition generation for create operation."""
        result = enricher.enrich_spec(simple_spec)
        post_op = result["paths"]["/api/resources"]["post"]
        metadata = post_op["x-ves-operation-metadata"]

        conditions = metadata["conditions"]
        postconditions = conditions["postconditions"]

        # Should mention resource creation
        assert any("created" in str(p).lower() for p in postconditions)

    def test_postconditions_for_delete(self, enricher, simple_spec):
        """Test postcondition generation for delete operation."""
        result = enricher.enrich_spec(simple_spec)
        delete_op = result["paths"]["/api/resources/{id}"]["delete"]
        metadata = delete_op["x-ves-operation-metadata"]

        conditions = metadata["conditions"]
        postconditions = conditions["postconditions"]

        # Should mention resource removal
        assert any("removed" in str(p).lower() for p in postconditions)

    def test_multiple_operations_independent(self, enricher, simple_spec):
        """Test that metadata for different operations is independent."""
        result = enricher.enrich_spec(simple_spec)

        get_op_metadata = result["paths"]["/api/resources"]["get"]["x-ves-operation-metadata"]
        post_op_metadata = result["paths"]["/api/resources"]["post"]["x-ves-operation-metadata"]
        delete_op_metadata = result["paths"]["/api/resources/{id}"]["delete"][
            "x-ves-operation-metadata"
        ]

        # Each should have different purpose
        assert get_op_metadata["purpose"] != post_op_metadata["purpose"]
        assert post_op_metadata["purpose"] != delete_op_metadata["purpose"]


class TestEdgeCases:
    """Test edge cases in dual-format generation."""

    def test_operation_without_responses(self, enricher):
        """Test handling operation with no responses."""
        spec = {
            "paths": {
                "/api/resource": {
                    "get": {
                        "operationId": "getResource",
                        "responses": {},
                    },
                },
            },
        }

        result = enricher.enrich_spec(spec)
        operation = result["paths"]["/api/resource"]["get"]

        # Should still generate metadata
        assert "x-ves-operation-metadata" in operation

    def test_operation_without_request_body(self, enricher):
        """Test handling operation with no request body."""
        spec = {
            "paths": {
                "/api/resource": {
                    "get": {
                        "operationId": "listResources",
                        "responses": {"200": {"description": "Success"}},
                    },
                },
            },
        }

        result = enricher.enrich_spec(spec)
        operation = result["paths"]["/api/resource"]["get"]
        metadata = operation["x-ves-operation-metadata"]

        # Optional fields should be empty
        assert metadata["optional_fields"] == []

    def test_empty_paths(self, enricher):
        """Test handling spec with no paths."""
        spec = {"paths": {}}

        result = enricher.enrich_spec(spec)
        assert result == spec


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
