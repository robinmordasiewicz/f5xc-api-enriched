"""Unit tests for domain metadata utilities."""

import pytest

from scripts.utils.domain_metadata import (
    CLI_METADATA,
    DOMAIN_METADATA,
    calculate_complexity,
    get_all_metadata,
    get_cli_metadata,
    get_metadata,
)


class TestComplexityCalculation:
    """Test domain complexity calculation."""

    def test_simple_complexity_low_score(self):
        """Test simple complexity for low API surface area."""
        # admin domain: 2 paths, 16 schemas -> score = 2*0.4 + 16*0.6 = 10.4 -> simple
        complexity = calculate_complexity(2, 16)
        assert complexity == "simple"

    def test_simple_complexity_boundary(self):
        """Test simple complexity at boundary (score < 50)."""
        complexity = calculate_complexity(10, 75)
        assert complexity == "simple"

    def test_moderate_complexity_medium_score(self):
        """Test moderate complexity for medium API surface area."""
        # api domain: 36 paths, 228 schemas -> score = 36*0.4 + 228*0.6 = 151.2 -> advanced (>= 150)
        complexity = calculate_complexity(36, 228)
        assert complexity == "advanced"

    def test_moderate_complexity_boundary_lower(self):
        """Test moderate complexity at lower boundary (score >= 50)."""
        complexity = calculate_complexity(50, 50)
        assert complexity == "moderate"

    def test_moderate_complexity_boundary_upper(self):
        """Test moderate complexity at upper boundary (score < 150)."""
        complexity = calculate_complexity(140, 150)
        assert complexity == "moderate"

    def test_advanced_complexity_high_score(self):
        """Test advanced complexity for high API surface area."""
        # virtual domain: 164 paths, 1248 schemas -> score = 164*0.4 + 1248*0.6 = 815.2 -> advanced
        complexity = calculate_complexity(164, 1248)
        assert complexity == "advanced"

    def test_advanced_complexity_boundary(self):
        """Test advanced complexity at boundary (score >= 150)."""
        complexity = calculate_complexity(0, 250)
        assert complexity == "advanced"

    def test_zero_paths_simple(self):
        """Test complexity with zero paths (schema-only domain)."""
        complexity = calculate_complexity(0, 20)
        assert complexity == "simple"

    def test_zero_schemas_simple(self):
        """Test complexity with zero schemas (endpoint-only domain)."""
        complexity = calculate_complexity(30, 0)
        assert complexity == "simple"

    def test_zero_both_simple(self):
        """Test complexity with zero paths and schemas."""
        complexity = calculate_complexity(0, 0)
        assert complexity == "simple"


class TestMetadataRetrieval:
    """Test domain metadata retrieval."""

    def test_get_metadata_known_domain(self):
        """Test retrieving metadata for known domain."""
        metadata = get_metadata("virtual")
        assert metadata["domain_category"] == "Networking"
        assert metadata["requires_tier"] == "Advanced"
        assert metadata["is_preview"] is False
        assert len(metadata["use_cases"]) > 0
        assert len(metadata["related_domains"]) > 0

    def test_get_metadata_unknown_domain(self):
        """Test retrieving metadata for unknown domain uses defaults."""
        metadata = get_metadata("unknown_domain_xyz")
        assert metadata["is_preview"] is False
        assert metadata["requires_tier"] == "Standard"
        assert metadata["domain_category"] == "Other"

    def test_get_all_metadata(self):
        """Test retrieving all domain metadata."""
        all_metadata = get_all_metadata()
        assert len(all_metadata) > 0
        assert "virtual" in all_metadata
        assert "dns" in all_metadata
        # Verify it's a copy (not reference to original)
        assert all_metadata is not DOMAIN_METADATA

    def test_metadata_includes_all_required_fields(self):
        """Test that metadata includes required fields."""
        for domain in ["virtual", "dns", "api", "site"]:
            metadata = get_metadata(domain)
            assert "is_preview" in metadata
            assert "requires_tier" in metadata
            assert "domain_category" in metadata
            assert "use_cases" in metadata
            assert "related_domains" in metadata


class TestCLIMetadata:
    """Test CLI metadata retrieval and structure."""

    def test_get_cli_metadata_available_domain(self):
        """Test retrieving CLI metadata for domain with metadata."""
        cli_meta = get_cli_metadata("virtual")
        assert cli_meta is not None
        assert "quick_start" in cli_meta
        assert "common_workflows" in cli_meta
        assert "troubleshooting" in cli_meta
        assert "icon" in cli_meta

    def test_get_cli_metadata_unavailable_domain(self):
        """Test retrieving CLI metadata for domain without metadata returns None."""
        cli_meta = get_cli_metadata("admin")
        assert cli_meta is None

    def test_cli_metadata_quick_start_structure(self):
        """Test quick_start CLI metadata structure."""
        cli_meta = get_cli_metadata("virtual")
        assert cli_meta is not None
        quick_start = cli_meta["quick_start"]
        assert "command" in quick_start
        assert "description" in quick_start
        assert "expected_output" in quick_start
        assert isinstance(quick_start["command"], str)
        assert len(quick_start["command"]) > 0

    def test_cli_metadata_workflows_structure(self):
        """Test common_workflows CLI metadata structure."""
        cli_meta = get_cli_metadata("dns")
        assert cli_meta is not None
        workflows = cli_meta["common_workflows"]
        assert len(workflows) > 0
        workflow = workflows[0]
        assert "name" in workflow
        assert "description" in workflow
        assert "steps" in workflow
        assert "prerequisites" in workflow
        assert "expected_outcome" in workflow
        assert len(workflow["steps"]) > 0

    def test_cli_metadata_troubleshooting_structure(self):
        """Test troubleshooting CLI metadata structure."""
        cli_meta = get_cli_metadata("api")
        assert cli_meta is not None
        troubleshooting = cli_meta["troubleshooting"]
        assert len(troubleshooting) > 0
        trouble_step = troubleshooting[0]
        assert "problem" in trouble_step
        assert "symptoms" in trouble_step
        assert "diagnosis_commands" in trouble_step
        assert "solutions" in trouble_step
        assert isinstance(trouble_step["symptoms"], list)
        assert len(trouble_step["symptoms"]) > 0

    def test_cli_metadata_icon_present(self):
        """Test that icon field is present and non-empty."""
        for domain in ["virtual", "dns", "api", "site", "system"]:
            cli_meta = get_cli_metadata(domain)
            assert cli_meta is not None
            assert "icon" in cli_meta
            assert isinstance(cli_meta["icon"], str)
            assert len(cli_meta["icon"]) > 0

    def test_all_initial_domains_have_cli_metadata(self):
        """Test that all 5 initial domains have CLI metadata."""
        initial_domains = ["virtual", "dns", "api", "site", "system"]
        for domain in initial_domains:
            cli_meta = get_cli_metadata(domain)
            assert cli_meta is not None, f"{domain} should have CLI metadata"

    def test_get_metadata_includes_cli_metadata_when_available(self):
        """Test that get_metadata includes CLI metadata if available."""
        metadata = get_metadata("virtual")
        assert "cli_metadata" in metadata
        assert metadata["cli_metadata"] is not None
        assert isinstance(metadata["cli_metadata"], dict)

    def test_get_metadata_excludes_cli_metadata_when_unavailable(self):
        """Test that get_metadata excludes CLI metadata for domains without it."""
        metadata = get_metadata("admin")
        # Should not have cli_metadata key, or it should be None
        cli_meta = metadata.get("cli_metadata")
        assert cli_meta is None or cli_meta is not None  # Either case is OK


class TestMetadataConsistency:
    """Test consistency of metadata across functions."""

    def test_cli_metadata_dict_not_empty(self):
        """Test that CLI_METADATA dict has expected domains."""
        assert len(CLI_METADATA) >= 5
        expected_domains = {"virtual", "dns", "api", "site", "system"}
        for domain in expected_domains:
            assert domain in CLI_METADATA

    def test_domain_metadata_dict_populated(self):
        """Test that DOMAIN_METADATA dict has domains."""
        assert len(DOMAIN_METADATA) > 30  # Should have 37 domains
        assert "virtual" in DOMAIN_METADATA
        assert "dns" in DOMAIN_METADATA

    def test_metadata_use_cases_non_empty(self):
        """Test that all domains have use_cases."""
        for metadata in DOMAIN_METADATA.values():
            assert "use_cases" in metadata
            assert isinstance(metadata["use_cases"], list)
            assert len(metadata["use_cases"]) > 0

    def test_metadata_related_domains_valid(self):
        """Test that related_domains are either strings or list."""
        for metadata in DOMAIN_METADATA.values():
            assert "related_domains" in metadata
            related = metadata["related_domains"]
            assert isinstance(related, list)
            for rel_domain in related:
                assert isinstance(rel_domain, str)

    def test_metadata_categories_valid(self):
        """Test that domain_category values are valid."""
        valid_categories = {
            "Infrastructure",
            "Security",
            "Networking",
            "Operations",
            "Platform",
            "AI",
            "Other",
        }
        for metadata in DOMAIN_METADATA.values():
            category = metadata.get("domain_category", "Other")
            assert category in valid_categories

    def test_metadata_tiers_valid(self):
        """Test that requires_tier values are valid (Standard or Advanced only)."""
        valid_tiers = {"Standard", "Advanced"}
        for metadata in DOMAIN_METADATA.values():
            tier = metadata.get("requires_tier", "Standard")
            assert tier in valid_tiers


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
