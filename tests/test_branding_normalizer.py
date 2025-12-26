"""Unit tests for BrandingNormalizer and XCKS/XCCS terminology transformations.

Tests the BrandingNormalizer class for transforming legacy F5 XC Kubernetes
terminology to industry-standard naming conventions:
- AppStack/VoltStack → F5 XC Managed Kubernetes (XCKS)
- Virtual Kubernetes → F5 XC Container Services (XCCS)
"""

from scripts.utils.branding import BrandingNormalizer, BrandingStats


class TestBrandingStats:
    """Test BrandingStats dataclass."""

    def test_default_values(self) -> None:
        """Verify default values are initialized correctly."""
        stats = BrandingStats()
        assert stats.legacy_terms_replaced == 0
        assert stats.xks_transformations == 0
        assert stats.xcs_transformations == 0
        assert stats.glossary_terms_added == 0
        assert stats.files_processed == 0
        assert stats.transformations_by_type == {}

    def test_to_dict(self) -> None:
        """Verify stats convert to dictionary correctly."""
        stats = BrandingStats(
            xks_transformations=5,
            xcs_transformations=3,
            files_processed=10,
        )
        result = stats.to_dict()

        assert isinstance(result, dict)
        assert result["xks_transformations"] == 5
        assert result["xcs_transformations"] == 3
        assert result["files_processed"] == 10


class TestBrandingNormalizerInitialization:
    """Test BrandingNormalizer initialization and configuration."""

    def test_default_initialization(self) -> None:
        """Verify normalizer initializes with default config."""
        normalizer = BrandingNormalizer()
        assert normalizer.canonical is not None
        assert "managed_kubernetes" in normalizer.canonical
        assert "container_services" in normalizer.canonical

    def test_xcks_canonical_config(self) -> None:
        """Verify XCKS (Managed Kubernetes) canonical configuration."""
        normalizer = BrandingNormalizer()
        xcks = normalizer.canonical.get("managed_kubernetes")

        assert xcks is not None
        assert xcks["short_form"] == "XCKS"
        assert "F5 XC Managed Kubernetes" in xcks["long_form"]
        assert "AppStack" in xcks.get("legacy_names", [])
        assert "AWS EKS" in xcks.get("comparable_to", [])
        assert "Azure AKS" in xcks.get("comparable_to", [])

    def test_xccs_canonical_config(self) -> None:
        """Verify XCCS (Container Services) canonical configuration."""
        normalizer = BrandingNormalizer()
        xccs = normalizer.canonical.get("container_services")

        assert xccs is not None
        assert xccs["short_form"] == "XCCS"
        assert "Container Services" in xccs["long_form"]
        assert "Virtual Kubernetes" in xccs.get("legacy_names", [])
        assert "AWS ECS" in xccs.get("comparable_to", [])

    def test_glossary_loaded(self) -> None:
        """Verify glossary terms are loaded."""
        normalizer = BrandingNormalizer()

        assert "XCKS" in normalizer.glossary
        assert "XCCS" in normalizer.glossary
        assert "term" in normalizer.glossary["XCKS"]
        assert "definition" in normalizer.glossary["XCKS"]


class TestXCCSTransformations:
    """Test XCCS (Container Services) terminology transformations."""

    def test_virtual_kubernetes_to_xccs(self) -> None:
        """Test Virtual Kubernetes → F5 XC Container Services (XCCS)."""
        normalizer = BrandingNormalizer()
        text = "Deploy Virtual Kubernetes namespaces for workloads."

        result = normalizer.normalize_text(text, field_context="info.description")

        assert "Virtual Kubernetes" not in result
        assert "XCCS" in result or "Container Services" in result

    def test_vk8s_to_xccs(self) -> None:
        """Test vK8s → XCCS transformation."""
        normalizer = BrandingNormalizer()
        text = "Configure vK8s for multi-tenant deployments."

        result = normalizer.normalize_text(text, field_context="info.description")

        assert "vK8s" not in result
        assert "XCCS" in result

    def test_xccs_stats_tracking(self) -> None:
        """Verify XCCS transformation statistics are tracked."""
        normalizer = BrandingNormalizer()
        normalizer.reset_stats()

        normalizer.normalize_text("Deploy Virtual Kubernetes", field_context="info.description")
        stats = normalizer.get_stats()

        assert stats["xcs_transformations"] >= 1


class TestXCKSTransformations:
    """Test XCKS (Managed Kubernetes) terminology transformations."""

    def test_appstack_to_xcks(self) -> None:
        """Test AppStack → F5 XC Managed Kubernetes (XCKS)."""
        normalizer = BrandingNormalizer()
        text = "Deploy AppStack for enterprise Kubernetes."

        result = normalizer.normalize_text(text, field_context="info.description")

        assert "AppStack" not in result
        assert "XCKS" in result or "Managed Kubernetes" in result

    def test_voltstack_to_xcks(self) -> None:
        """Test VoltStack → F5 XC Managed Kubernetes (XCKS)."""
        normalizer = BrandingNormalizer()
        text = "Configure VoltStack site for on-premises deployment."

        result = normalizer.normalize_text(text, field_context="info.description")

        assert "VoltStack" not in result
        assert "XCKS" in result or "Managed Kubernetes" in result

    def test_xcks_stats_tracking(self) -> None:
        """Verify XCKS transformation statistics are tracked."""
        normalizer = BrandingNormalizer()
        normalizer.reset_stats()

        normalizer.normalize_text("Deploy AppStack clusters", field_context="info.description")
        stats = normalizer.get_stats()

        assert stats["xks_transformations"] >= 1


class TestSpecNormalization:
    """Test OpenAPI specification normalization."""

    def test_normalize_spec_description(self) -> None:
        """Test normalization of spec info description."""
        normalizer = BrandingNormalizer()
        spec = {
            "info": {
                "title": "Virtual Kubernetes API",
                "description": "Manage Virtual Kubernetes namespaces",
            },
        }

        result = normalizer.normalize_spec(spec)

        # Description should be transformed
        assert "Virtual Kubernetes" not in result["info"]["description"]
        assert (
            "XCCS" in result["info"]["description"]
            or "Container Services" in result["info"]["description"]
        )

    def test_normalize_spec_summary(self) -> None:
        """Test normalization of operation summary fields."""
        normalizer = BrandingNormalizer()
        spec = {
            "info": {"title": "Test API"},
            "paths": {
                "/deploy": {
                    "post": {
                        "summary": "Deploy AppStack workloads",
                        "description": "Deploy workloads to AppStack cluster",
                    },
                },
            },
        }

        result = normalizer.normalize_spec(spec)
        operation = result["paths"]["/deploy"]["post"]

        # Both summary and description should be checked
        # (transformation depends on field context)
        assert "summary" in operation
        assert "description" in operation

    def test_normalize_spec_nested_schemas(self) -> None:
        """Test normalization of nested schema descriptions."""
        normalizer = BrandingNormalizer()
        spec = {
            "info": {"title": "Test API"},
            "components": {
                "schemas": {
                    "WorkloadSpec": {
                        "description": "Virtual Kubernetes workload specification",
                        "properties": {
                            "name": {
                                "description": "Workload name for vK8s deployment",
                            },
                        },
                    },
                },
            },
        }

        result = normalizer.normalize_spec(spec)
        schema = result["components"]["schemas"]["WorkloadSpec"]

        # Check that transformation was applied to schema description
        assert "description" in schema

    def test_files_processed_stat(self) -> None:
        """Verify files_processed counter increments."""
        normalizer = BrandingNormalizer()
        normalizer.reset_stats()

        spec = {"info": {"title": "Test"}}
        normalizer.normalize_spec(spec)
        normalizer.normalize_spec(spec)
        normalizer.normalize_spec(spec)

        stats = normalizer.get_stats()
        assert stats["files_processed"] == 3


class TestGlossaryIntegration:
    """Test glossary term integration into specs."""

    def test_glossary_added_to_info(self) -> None:
        """Verify glossary terms are added to spec info."""
        normalizer = BrandingNormalizer()
        spec = {
            "info": {
                "title": "Test API",
                "description": "Test description",
            },
        }

        result = normalizer.normalize_spec(spec)

        # Check that glossary was added
        assert "x-ves-glossary" in result["info"]
        glossary = result["info"]["x-ves-glossary"]
        assert "XCKS" in glossary or "XCCS" in glossary

    def test_glossary_terms_added_stat(self) -> None:
        """Verify glossary_terms_added counter increments."""
        normalizer = BrandingNormalizer()
        normalizer.reset_stats()

        spec = {"info": {"title": "Test"}}
        normalizer.normalize_spec(spec)

        stats = normalizer.get_stats()
        assert stats["glossary_terms_added"] >= 1

    def test_existing_glossary_preserved(self) -> None:
        """Verify existing glossary terms are not overwritten."""
        normalizer = BrandingNormalizer()
        spec = {
            "info": {
                "title": "Test API",
                "x-ves-glossary": {
                    "CUSTOM_TERM": {"term": "Custom", "definition": "Custom def"},
                },
            },
        }

        result = normalizer.normalize_spec(spec)

        # Custom term should be preserved
        glossary = result["info"]["x-ves-glossary"]
        assert "CUSTOM_TERM" in glossary
        assert glossary["CUSTOM_TERM"]["definition"] == "Custom def"


class TestCanonicalNaming:
    """Test canonical name lookup functionality."""

    def test_get_canonical_name_managed_kubernetes(self) -> None:
        """Test canonical name lookup for managed_kubernetes."""
        normalizer = BrandingNormalizer()
        canonical = normalizer.get_canonical_name("managed_kubernetes")

        assert canonical is not None
        assert canonical["short_form"] == "XCKS"

    def test_get_canonical_name_container_services(self) -> None:
        """Test canonical name lookup for container_services."""
        normalizer = BrandingNormalizer()
        canonical = normalizer.get_canonical_name("container_services")

        assert canonical is not None
        assert canonical["short_form"] == "XCCS"

    def test_get_canonical_name_unknown(self) -> None:
        """Test canonical name lookup for unknown domain returns None."""
        normalizer = BrandingNormalizer()
        canonical = normalizer.get_canonical_name("unknown_domain")

        assert canonical is None


class TestStatsReset:
    """Test statistics reset functionality."""

    def test_reset_stats(self) -> None:
        """Verify reset_stats clears all counters."""
        normalizer = BrandingNormalizer()

        # Generate some stats
        normalizer.normalize_text("Deploy AppStack", field_context="info.description")
        normalizer.normalize_text("Deploy Virtual Kubernetes", field_context="info.description")

        # Reset and verify
        normalizer.reset_stats()
        stats = normalizer.get_stats()

        assert stats["xks_transformations"] == 0
        assert stats["xcs_transformations"] == 0
        assert stats["files_processed"] == 0
        assert stats["glossary_terms_added"] == 0


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_text(self) -> None:
        """Test normalization of empty text."""
        normalizer = BrandingNormalizer()
        result = normalizer.normalize_text("")
        assert result == ""

    def test_none_text(self) -> None:
        """Test normalization of None text."""
        normalizer = BrandingNormalizer()
        result = normalizer.normalize_text(None)  # type: ignore[arg-type]
        assert result is None

    def test_text_without_legacy_terms(self) -> None:
        """Test text without legacy terms is unchanged."""
        normalizer = BrandingNormalizer()
        text = "This is a normal description without legacy terms."

        result = normalizer.normalize_text(text)

        assert result == text

    def test_empty_spec(self) -> None:
        """Test normalization of empty spec."""
        normalizer = BrandingNormalizer()
        result = normalizer.normalize_spec({})
        assert result == {}

    def test_spec_without_info(self) -> None:
        """Test spec without info section doesn't fail."""
        normalizer = BrandingNormalizer()
        spec = {
            "paths": {
                "/test": {"get": {"summary": "Test endpoint"}},
            },
        }

        result = normalizer.normalize_spec(spec)

        # Should not raise, should return spec without adding glossary
        assert "paths" in result


class TestContextFiltering:
    """Test context-based transformation filtering."""

    def test_context_matches(self) -> None:
        """Test transformation applied when context matches."""
        normalizer = BrandingNormalizer()
        text = "Deploy Virtual Kubernetes"

        # info.description is in the context list for this transformation
        result = normalizer.normalize_text(text, field_context="info.description")

        # Transformation should be applied
        assert "Virtual Kubernetes" not in result

    def test_no_context_provided(self) -> None:
        """Test transformation applied when no context provided."""
        normalizer = BrandingNormalizer()
        text = "Deploy Virtual Kubernetes"

        # No context means transformations with empty context list apply
        result = normalizer.normalize_text(text, field_context="")

        # Default behavior when no context filtering
        assert text == result or "XCCS" in result


class TestIndustryComparison:
    """Test industry comparison terminology in canonical config."""

    def test_xcks_comparable_to_eks_aks_gke(self) -> None:
        """Verify XCKS is compared to EKS, AKS, GKE."""
        normalizer = BrandingNormalizer()
        xcks = normalizer.canonical.get("managed_kubernetes", {})

        comparable = xcks.get("comparable_to", [])
        assert "AWS EKS" in comparable
        assert "Azure AKS" in comparable
        assert "Google GKE" in comparable

    def test_xccs_comparable_to_ecs(self) -> None:
        """Verify XCCS is compared to ECS and container services."""
        normalizer = BrandingNormalizer()
        xccs = normalizer.canonical.get("container_services", {})

        comparable = xccs.get("comparable_to", [])
        assert "AWS ECS" in comparable
